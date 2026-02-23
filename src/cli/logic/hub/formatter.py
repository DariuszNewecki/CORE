# src/body/cli/logic/hub/formatter.py

"""Refactored logic for src/body/cli/logic/hub/formatter.py."""

from __future__ import annotations

from shared.infrastructure.database.models import CliCommand


# ID: 37128525-8c6d-4e5e-84e5-2db260d59b54
def format_name(cmd: CliCommand) -> str:
    return getattr(cmd, "name", "") or ""


# ID: ca841d77-9d0c-4f83-bfbf-2885a0830f62
def shorten(s: str | None, n: int = 80) -> str:
    if not s:
        return "—"
    return s if len(s) <= n else s[: n - 1] + "…"


# ID: aa7aaa22-3e36-4464-b7ed-ec59aecc0e2c
def get_description(c: CliCommand) -> str:
    """Best-effort description retrieval across possible schema variations."""
    for attr in ("description", "help", "summary", "doc"):
        v = getattr(c, attr, None)
        if isinstance(v, str) and v.strip():
            return v
    return ""
