# src/shared/infrastructure/cli_session.py
"""Persistent CLI session store for governor credentials (ADR-132).

Writes to ~/.config/core/session.json (mode 0o600). Stores the
core_access JWT and core_refresh token so CoreApiClient can attach
them as cookies on every request without requiring a per-invocation
login step.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


_SESSION_DIR = Path.home() / ".config" / "core"
_SESSION_FILE = _SESSION_DIR / "session.json"


# ID: e7d52d5e-62d2-4800-94d2-16cf02e9d9d4
def load_session() -> dict | None:
    """Return stored session dict or None if absent / unreadable."""
    try:
        return json.loads(_SESSION_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


# ID: c557ebf6-50a1-4205-aba4-2e9faf6b32a7
def save_session(access_token: str, refresh_token: str) -> None:
    """Persist tokens to the session file (mode 0o600)."""
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
    _SESSION_FILE.write_text(data)
    os.chmod(_SESSION_FILE, 0o600)


# ID: c7e017e8-ee59-4fdf-a472-0f76e1728daf
def clear_session() -> None:
    """Remove the session file if it exists."""
    try:
        _SESSION_FILE.unlink()
    except FileNotFoundError:
        pass
