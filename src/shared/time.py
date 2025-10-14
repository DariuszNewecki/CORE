# src/shared/time.py
"""
Lightweight time utilities shared across services.
Implements the canonical capability for a UTC ISO timestamp function.
"""

from __future__ import annotations

from datetime import UTC, datetime


# ID: 4f686bb3-7252-4f74-8e7c-d38a6ec85dc6
def now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


# A trivial change for testing.
