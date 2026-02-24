import json
import os
import time
import secrets
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_QUOTES_DIR = os.environ.get("QUOTES_DIR", "/app/data/quotes")

def _now_ts() -> int:
    return int(time.time())

def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

class QuotesStore:
    def __init__(self, base_dir: str = DEFAULT_QUOTES_DIR):
        self.base = Path(base_dir)

    def new_id(self) -> str:
        return f"q_{secrets.token_hex(12)}"

    def quote_dir(self, quote_id: str) -> Path:
        return self.base / quote_id

    def quote_path(self, quote_id: str) -> Path:
        return self.quote_dir(quote_id) / "quote.json"

    def save(self, quote_id: str, quote: Dict[str, Any]) -> None:
        _atomic_write_json(self.quote_path(quote_id), quote)

    def load(self, quote_id: str) -> Optional[Dict[str, Any]]:
        p = self.quote_path(quote_id)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def exists(self, quote_id: str) -> bool:
        return self.quote_path(quote_id).exists()

    def is_expired(self, quote: Dict[str, Any]) -> bool:
        exp = quote.get("expiresAtTs")
        return isinstance(exp, int) and _now_ts() > exp

    def now(self) -> int:
        return _now_ts()