import json
import os
import time
import secrets
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

QUOTE_ID_RE = re.compile(r"^q_[0-9a-f]{24}$")
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
        if not QUOTE_ID_RE.match(quote_id):
            raise ValueError("invalid quote id")
        return self.base / quote_id

    def quote_path(self, quote_id: str) -> Path:
        return self.quote_dir(quote_id) / "quote.json"

    def load(self, quote_id: str) -> Optional[Dict[str, Any]]:
        try:
            p = self.quote_path(quote_id)
        except ValueError:
            return None
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def exists(self, quote_id: str) -> bool:
        try:
            return self.quote_path(quote_id).exists()
        except ValueError:
            return False

    def save(self, quote_id: str, quote: Dict[str, Any]) -> None:
        # save sólo lo llamas con ids generados por ti, pero por seguridad:
        _atomic_write_json(self.quote_path(quote_id), quote)

    def is_expired(self, quote: Dict[str, Any]) -> bool:
        exp = quote.get("expiresAtTs")
        return isinstance(exp, int) and _now_ts() > exp

    def now(self) -> int:
        return _now_ts()