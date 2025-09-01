# src/example/untagged_demo_helper.py
"""Tiny helper used for the seminar demo.

Intentionally missing a capability tag so the Auditor can flag it.
This keeps other style checks happy, so you only see one violation.
"""
from __future__ import annotations

from typing import Iterable


# CAPABILITY: utils.text.process_lines
def untagged_demo_helper(lines: Iterable[str]) -> list[str]:
    """Return non-empty, stripped lines (toy logic for the demo)."""
    return [s.strip() for s in lines if s.strip()]
