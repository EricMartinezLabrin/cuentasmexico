import json
import os
import threading
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone


WHATSAPP_DELIVERY_LOG_FILE = "whatsapp_delivery_history.jsonl"
_log_lock = threading.Lock()


def _log_path() -> str:
    logs_dir = os.path.join(settings.BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, WHATSAPP_DELIVERY_LOG_FILE)


def append_whatsapp_delivery_log(entry: Dict):
    payload = dict(entry or {})
    payload.setdefault("timestamp", timezone.now().isoformat())
    payload.setdefault("event", "unknown")
    payload.setdefault("level", "info")
    with _log_lock:
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def read_whatsapp_delivery_log(
    limit: int = 200,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict]:
    path = _log_path()
    if not os.path.exists(path):
        return []

    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue

            day = str(row.get("timestamp") or "")[:10]
            if date_from and day and day < date_from:
                continue
            if date_to and day and day > date_to:
                continue
            rows.append(row)

    return list(reversed(rows[-max(1, limit):]))
