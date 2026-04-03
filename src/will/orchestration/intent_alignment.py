# src/will/orchestration/intent_alignment.py
"""
Lightweight guard to ensure a requested goal aligns with CORE's mission/scope.

- Loads NorthStar text via IntentRepository (governed access, no direct filesystem).
- Returns (ok: bool, details: dict) with short reason codes only.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path


log = logging.getLogger(__name__)

_NORTHSTAR_REL = "northstar/core_northstar.md"


def _read_northstar() -> str:
    """Reads NorthStar text via IntentRepository. Returns empty string on failure."""
    try:
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        return get_intent_repository().load_text(_NORTHSTAR_REL)
    except Exception:
        log.debug("NorthStar not available at %s", _NORTHSTAR_REL, exc_info=True)
        return ""


def _tokenize(text: str) -> list[str]:
    """Converts a string into a list of lowercase alphanumeric tokens."""
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


# ID: f1267ace-1e0a-47f8-8d81-36ce4262913a
def check_goal_alignment(
    goal: str, project_root: Path = Path(".")
) -> tuple[bool, dict]:
    """
    Returns (ok, details). details = { 'coverage': float|None, 'violations': [codes...] }
    Violation codes: 'low_mission_overlap'
    """
    violations: list[str] = []
    mission = _read_northstar()

    coverage = None
    if mission:
        g_tokens = set(_tokenize(goal))
        m_tokens = set(_tokenize(mission))
        if g_tokens:
            overlap = len(g_tokens & m_tokens)
            coverage = round(overlap / max(1, len(g_tokens)), 3)
            if coverage < 0.10:
                violations.append("low_mission_overlap")

    ok = not violations
    return ok, {"coverage": coverage, "violations": violations}
