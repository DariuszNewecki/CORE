# src/will/audit_violation/governor_alarms.py
"""Open findings that stop CORE's own work and only the governor can clear.

On 2026-10-22 the stale-clone finding sat unseen for 7 hours (#1243). The
daily promotion is what the governor reads, so ``promote propose`` puts
these on top of its summary.
"""

from __future__ import annotations

from body.services.blackboard_service.blackboard_query_service import (
    BlackboardQueryService,
)

from .staleness import STALE_SUBJECT


ALARMS = {
    STALE_SUBJECT: (
        "CORE's working copy (`/opt/core/repo`) is behind main, so it audits "
        "old code and writes no tests. Reset it to main: `sudo -u core git -C "
        "/opt/core/repo fetch -q origin main && sudo -u core git -C "
        "/opt/core/repo reset --hard origin/main`"
    ),
}


# ID: 74e96565-a999-45e4-9b45-82a1d653b7d1
async def open_alarms() -> list[str]:
    """The plain-words text of each alarm whose finding is open. A board
    that cannot be read is itself an alarm."""
    try:
        board = BlackboardQueryService()
        return [
            text
            for subject, text in ALARMS.items()
            if await board.fetch_open_finding_subjects_by_prefix(subject)
        ]
    except Exception as exc:
        return [f"CORE could not read its open findings: {type(exc).__name__}: {exc}"]
