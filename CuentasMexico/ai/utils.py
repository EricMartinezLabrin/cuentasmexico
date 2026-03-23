from __future__ import annotations

import base64
from typing import Any


def b64_encode(value: bytes | str) -> str:
    if isinstance(value, str):
        return value
    return base64.b64encode(value).decode("utf-8")


def b64_decode(value: str) -> bytes:
    return base64.b64decode(value)


def is_url(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def safe_get(dct: Any, *keys: str, default=None):
    current = dct
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current
