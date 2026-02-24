import hmac
import hashlib
import os
import json
from typing import Any, Dict

HMAC_SECRET = os.environ.get("QUOTE_HMAC_SECRET") or os.environ.get("SECRET_KEY") or "dev-secret"


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

def sign_quote(payload: Dict[str, Any]) -> str:
    params_hash = hashlib.sha256(_stable_json(payload.get("params", {})).encode("utf-8")).hexdigest()
    computed_hash = hashlib.sha256(_stable_json(payload.get("computed", {})).encode("utf-8")).hexdigest()

    msg = "|".join([
        str(payload.get("quoteId", "")),
        str(payload.get("status", "")),
        str(payload.get("price", "")),
        str(payload.get("currency", "")),
        str(payload.get("configVersion", "")),
        str(payload.get("expiresAtTs", "")),
        params_hash,
        computed_hash,
    ]).encode("utf-8")
    return hmac.new(HMAC_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_quote(payload: Dict[str, Any], signature: str) -> bool:
    expected = sign_quote(payload)
    return hmac.compare_digest(expected, signature or "")