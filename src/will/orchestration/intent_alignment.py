# src/will/orchestration/intent_alignment.py
"""
Lightweight guard to ensure a requested goal aligns with CORE's mission/scope.

- Loads NorthStar/mission text from .intent (best-effort; no hard failures).
- Optional blocklist: .intent/policies/blocked_topics.txt (one term per line).
- Returns (ok: bool, details: dict) with short reason codes only.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_INTENT_PATH_CANDIDATES: list[Path] = [
    Path(".intent/mission/northstar.md"),
    Path(".intent/mission/mission.md"),
    Path(".intent/mission/northstar.txt"),
    Path(".intent/NorthStar.md"),
]

_BLOCKLIST_PATH = Path(".intent/policies/blocked_topics.txt")


def _read_text_first(paths: list[Path]) -> str:
    """Finds and reads the first existing file from a list of candidate paths."""
    for p in paths:
        try:
            if p.exists():
                return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            log.debug("Failed reading %s", p, exc_info=True)
    return ""


def _read_blocklist() -> list[str]:
    """Reads the blocklist file, returning a list of lowercased, stripped terms."""
    if _BLOCKLIST_PATH.exists():
        try:
            return [
                ln.strip().lower()
                for ln in _BLOCKLIST_PATH.read_text(
                    encoding="utf-8", errors="ignore"
                ).splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
        except Exception:
            log.debug("Failed reading blocklist at %s", _BLOCKLIST_PATH, exc_info=True)
    return []


def _tokenize(text: str) -> list[str]:
    """Converts a string into a list of lowercase alphanumeric tokens."""
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


# ID: f1267ace-1e0a-47f8-8d81-36ce4262913a
def check_goal_alignment(
    goal: str, project_root: Path = Path(".")
) -> tuple[bool, dict]:
    """
    Returns (ok, details). details = { 'coverage': float|None, 'violations': [codes...] }
    Violations codes: 'blocked_topic', 'low_mission_overlap'
    """
    violations: list[str] = []
    mission = _read_text_first(_INTENT_PATH_CANDIDATES)
    blocked = _read_blocklist()

    # Blocklist
    goal_l = goal.lower()
    if blocked and any(term in goal_l for term in blocked):
        violations.append("blocked_topic")

    # Mission overlap (very simple lexical overlap)
    coverage = None
    if mission:
        g_tokens = set(_tokenize(goal))
        m_tokens = set(_tokenize(mission))
        if g_tokens:
            overlap = len(g_tokens & m_tokens)
            coverage = round(overlap / max(1, len(g_tokens)), 3)
            if coverage < 0.10:  # conservative default; tune later
                violations.append("low_mission_overlap")

    ok = not violations
    return ok, {"coverage": coverage, "violations": violations}
