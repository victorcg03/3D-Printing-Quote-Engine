import hmac
import hashlib
import os
from typing import Any, Dict

HMAC_SECRET = os.environ.get("QUOTE_HMAC_SECRET") or os.environ.get("SECRET_KEY") or "dev-secret"

def sign_quote(payload: Dict[str, Any]) -> str:
    """
    Firma solo campos críticos, no todo el JSON.
    """
    msg = "|".join([
        str(payload.get("quoteId", "")),
        str(payload.get("status", "")),
        str(payload.get("price", "")),
        str(payload.get("currency", "")),
        str(payload.get("configVersion", "")),
        str(payload.get("expiresAtTs", "")),
    ]).encode("utf-8")

    return hmac.new(HMAC_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def verify_quote(payload: Dict[str, Any], signature: str) -> bool:
    expected = sign_quote(payload)
    return hmac.compare_digest(expected, signature or "")