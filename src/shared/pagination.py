# src/shared/pagination.py

"""Keyset pagination cursor helpers — encode/decode only, no DB logic."""

from __future__ import annotations

import base64
import json
from datetime import datetime


# ID: cc61b44e-bbce-4a5b-9ae4-e45312e59fa0
def encode_cursor(ts: datetime | None, key: str) -> str:
    """Encode a keyset cursor as a URL-safe base64 string.

    `ts` is the sort timestamp (None for ID-only cursors).
    `key` is a string that uniquely identifies the row in secondary-sort order.
    """
    payload: dict[str, str] = {"k": key}
    if ts is not None:
        payload["t"] = ts.isoformat()
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()


# ID: 8cf79712-46f7-41f3-bd35-2a4d81ad430f
def decode_cursor(cursor: str) -> tuple[datetime | None, str]:
    """Decode a cursor produced by encode_cursor.

    Returns (ts, key). ts is None for ID-only cursors.
    Raises ValueError on malformed input.
    """
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        ts = datetime.fromisoformat(data["t"]) if "t" in data else None
        return ts, data["k"]
    except (KeyError, ValueError, Exception) as exc:
        raise ValueError(f"Invalid pagination cursor: {cursor!r}") from exc
