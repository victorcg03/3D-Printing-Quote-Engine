# test-e2e.ps1
# End-to-end smoke tests for Machine Shop Suite / 3D Printing Quote Engine
# - Builds & starts docker compose
# - Waits for /api/config health
# - Exercises /api/quotes create/get/lock/refresh
# - Stops containers even on failure
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\test-e2e.ps1
#   pwsh -File .\test-e2e.ps1
#
# Optional env:
#   $env:COMPOSE_FILE = "docker-compose.yml"          # override compose file
#   $env:SERVICE_URL  = "http://localhost:5000"       # override base URL
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ----------------------------
# Logging
# ----------------------------
function Write-Info([string]$msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }

# ----------------------------
# Assertions (truthy-safe)
# ----------------------------
function Assert {
  param(
    [Parameter(Mandatory = $true)][object]$Condition,
    [Parameter(Mandatory = $true)][string]$Message
  )

  # Convert to boolean safely (PowerShell truthiness)
  if (-not [bool]$Condition) {
    throw $Message
  }
}

function Assert-Equal {
  param(
    [Parameter(Mandatory = $true)][object]$Actual,
    [Parameter(Mandatory = $true)][object]$Expected,
    [Parameter(Mandatory = $true)][string]$Message
  )
  if ($Actual -ne $Expected) {
    throw "$Message (actual: '$Actual', expected: '$Expected')"
  }
}

function Has-Prop {
  param(
    [Parameter(Mandatory = $true)][object]$Obj,
    [Parameter(Mandatory = $true)][string]$Name
  )
  if ($null -eq $Obj) { return $false }
  return ($Obj.PSObject.Properties.Name -contains $Name)
}

# ----------------------------
# Compose / Docker
# ----------------------------
function Resolve-ComposeFile {
  if ($env:COMPOSE_FILE -and (Test-Path $env:COMPOSE_FILE)) { return $env:COMPOSE_FILE }
  if (Test-Path ".\docker-compose.yml") { return ".\docker-compose.yml" }
  throw "docker-compose.yml not found in current directory and COMPOSE_FILE not set."
}

function Ensure-Docker {
  try {
    docker version | Out-Null
  } catch {
    throw "Docker does not seem to be available. Install Docker Desktop and ensure it's running."
  }
}

function Docker-Compose-Up {
  param([Parameter(Mandatory=$true)][string]$ComposeFile)
  Write-Info "Building & starting compose ($ComposeFile)..."
  docker compose -f $ComposeFile up -d --build | Out-Host
}

function Docker-Compose-Down {
  param([Parameter(Mandatory=$true)][string]$ComposeFile)
  Write-Info "Stopping containers..."
  try {
    docker compose -f $ComposeFile down --remove-orphans | Out-Host
  } catch {
    Write-Warn "docker compose down failed: $($_.Exception.Message)"
  }
}

# ----------------------------
# HTTP helpers
# ----------------------------
function Invoke-HttpJson {
  param(
    [Parameter(Mandatory=$true)][string]$Method,
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$false)][object]$Body = $null,
    [Parameter(Mandatory=$false)][hashtable]$Headers = @{},
    [Parameter(Mandatory=$false)][int]$TimeoutSec = 30
  )

  $params = @{
    Method      = $Method
    Uri         = $Url
    Headers     = $Headers
    TimeoutSec  = $TimeoutSec
    ErrorAction = "Stop"
  }

  if ($null -ne $Body) {
    $params["ContentType"] = "application/json"
    $params["Body"] = ($Body | ConvertTo-Json -Depth 30)
  }

  try {
    return Invoke-RestMethod @params
  } catch {
    # Surface error body if possible
    $resp = $_.Exception.Response
    if ($resp -and $resp.GetResponseStream()) {
      try {
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $text = $reader.ReadToEnd()
        if ($text) { Write-Warn "HTTP error body: $text" }
      } catch { }
    }
    throw
  }
}

function Get-HttpStatusCode {
  param(
    [Parameter(Mandatory=$true)][string]$Method,
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$false)][object]$Body = $null,
    [Parameter(Mandatory=$false)][hashtable]$Headers = @{},
    [Parameter(Mandatory=$false)][int]$TimeoutSec = 30
  )

  $json = $null
  $status = $null
  $raw = $null

  try {
    $req = [System.Net.HttpWebRequest]::Create($Url)
    $req.Method = $Method
    $req.Timeout = $TimeoutSec * 1000
    foreach ($k in $Headers.Keys) { $req.Headers.Add($k, $Headers[$k]) }

    if ($null -ne $Body) {
      $payload = ($Body | ConvertTo-Json -Depth 30)
      $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
      $req.ContentType = "application/json"
      $req.ContentLength = $bytes.Length
      $stream = $req.GetRequestStream()
      $stream.Write($bytes, 0, $bytes.Length)
      $stream.Close()
    }

    $resp = $req.GetResponse()
    $status = [int]$resp.StatusCode
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $raw = $reader.ReadToEnd()
    $reader.Close()
    $resp.Close()

    if ($raw) {
      try { $json = $raw | ConvertFrom-Json } catch { $json = $null }
    }
  }
  catch [System.Net.WebException] {
    $resp = $_.Exception.Response
    if ($resp) {
      $status = [int]$resp.StatusCode
      try {
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $raw = $reader.ReadToEnd()
        $reader.Close()
        if ($raw) {
          try { $json = $raw | ConvertFrom-Json } catch { $json = $null }
        }
      } catch { }
      $resp.Close()
    } else {
      throw
    }
  }

  return [pscustomobject]@{
    Status = $status
    Json   = $json
    Raw    = $raw
  }
}

function Wait-ForHealthy {
  param(
    [Parameter(Mandatory=$true)][string]$BaseUrl,
    [int]$MaxSeconds = 120
  )

  $deadline = (Get-Date).AddSeconds($MaxSeconds)
  $healthUrl = "$BaseUrl/api/config"

  while ((Get-Date) -lt $deadline) {
    try {
      $r = Get-HttpStatusCode -Method "GET" -Url $healthUrl -TimeoutSec 5
      if ($r.Status -eq 200 -and $r.Json -and (Has-Prop $r.Json "success") -and $r.Json.success -eq $true) {
        Write-Ok "Service healthy at $BaseUrl"
        return
      }
    } catch { }
    Start-Sleep -Seconds 2
  }

  throw "Service did not become healthy within $MaxSeconds seconds ($healthUrl)."
}

# ----------------------------
# Main
# ----------------------------
$composeFile = Resolve-ComposeFile
$baseUrl = if ($env:SERVICE_URL) { $env:SERVICE_URL } else { "http://localhost:5000" }

Ensure-Docker

$failed = $false
try {
  Docker-Compose-Up -ComposeFile $composeFile
  Wait-ForHealthy -BaseUrl $baseUrl -MaxSeconds 120

  # ----------------------------
  # TEST 1: GET /api/config
  # ----------------------------
  Write-Info "TEST 1: GET /api/config"
  $cfg = Invoke-HttpJson -Method "GET" -Url "$baseUrl/api/config"
  Assert ((Has-Prop $cfg "success") -and $cfg.success -eq $true) "/api/config success should be true"
  Assert (Has-Prop $cfg "config") "/api/config should return config object"
  Write-Ok "api/config OK"

  # ----------------------------
  # TEST 2: POST /api/quotes (valid)
  # ----------------------------
  Write-Info "TEST 2: POST /api/quotes (valid)"
  $createBody = @{
    params = @{
      material       = "pla"
      quality        = "standard"
      printer        = "prusa_mk3s"
      qty            = 1
      infill_density = 20
    }
    computed = @{
      price    = 12.34
      currency = "EUR"
    }
  }

  $created = Invoke-HttpJson -Method "POST" -Url "$baseUrl/api/quotes" -Body $createBody
  Assert ((Has-Prop $created "success") -and $created.success -eq $true) "create quote should succeed"
  Assert (Has-Prop $created "quote") "create quote should include quote"
  Assert (Has-Prop $created.quote "quoteId") "quoteId missing"
  Assert (Has-Prop $created.quote "signature") "signature missing"

  $quoteId = [string]$created.quote.quoteId
  $signature = [string]$created.quote.signature
  Assert ($quoteId.Length -gt 0) "quoteId empty"
  Assert ($signature.Length -gt 0) "signature empty"
  Write-Ok "Created quote: $quoteId"

  # ----------------------------
  # TEST 3: GET /api/quotes/{id}
  # ----------------------------
  Write-Info "TEST 3: GET /api/quotes/{id}"
  $got = Invoke-HttpJson -Method "GET" -Url "$baseUrl/api/quotes/$quoteId"
  Assert ((Has-Prop $got "success") -and $got.success -eq $true) "get quote should succeed"
  Assert (Has-Prop $got "quote") "get quote should include quote"
  Assert-Equal $got.quote.quoteId $quoteId "get quote should return same id"
  Assert (Has-Prop $got.quote "signature") "signature should exist on fetched quote"
  Write-Ok "Get quote OK"

  # ----------------------------
  # TEST 4: LOCK quote with valid signature
  # ----------------------------
  Write-Info "TEST 4: LOCK quote with valid signature"
  $lockBody = @{ signature = $got.quote.signature }
  $locked = Invoke-HttpJson -Method "POST" -Url "$baseUrl/api/quotes/$quoteId/lock" -Body $lockBody
  Assert ((Has-Prop $locked "success") -and $locked.success -eq $true) "lock should succeed"
  Assert (Has-Prop $locked "quote") "lock should include quote"
  Assert (Has-Prop $locked.quote "status") "lock response missing status"
  Assert-Equal $locked.quote.status "locked" "status should be locked"
  Write-Ok "Lock OK"

  # ----------------------------
  # TEST 5: REFRESH locked -> 409
  # ----------------------------
  Write-Info "TEST 5: REFRESH locked -> 409"
  $refreshLocked = Get-HttpStatusCode -Method "POST" -Url "$baseUrl/api/quotes/$quoteId/refresh" -Body @{} -TimeoutSec 20
  Assert-Equal $refreshLocked.Status 409 "refresh locked should return HTTP 409"
  if ($refreshLocked.Json -and (Has-Prop $refreshLocked.Json "success")) {
    Assert ($refreshLocked.Json.success -eq $false) "refresh locked JSON success should be false"
  }
  Write-Ok "Refresh locked returns 409 as expected"

  Write-Ok "All tests passed ✅"
}
catch {
  $failed = $true
  Write-Err $_.Exception.Message
  throw
}
finally {
  Docker-Compose-Down -ComposeFile $composeFile
  if ($failed) {
    Write-Err "E2E tests failed ❌ (containers stopped)"
  } else {
    Write-Ok "E2E finished (containers stopped)"
  }
}