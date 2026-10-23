# src/will/audit_violation/governor_alarms.py
"""Open findings that stop CORE's own work and only the governor can clear.

On 2026-10-22 the stale-clone finding sat unseen for 7 hours (#1243). The
daily promotion is what the governor reads, so ``promote propose`` puts
these on top of its summary. The deploy ledger's last line is read too: a dev
checkout that did not follow the deploy sat unseen for 5 days (#1246).
"""

from __future__ import annotations

import json
from pathlib import Path

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
async def open_alarms(ledger: Path | None = None) -> list[str]:
    """The plain-words text of each alarm whose finding is open, then the
    deploy ledger's when one is given. A board that cannot be read is itself
    an alarm."""
    try:
        board = BlackboardQueryService()
        found = [
            text
            for subject, text in ALARMS.items()
            if await board.fetch_open_finding_subjects_by_prefix(subject)
        ]
    except Exception as exc:
        found = [f"CORE could not read its open findings: {type(exc).__name__}: {exc}"]
    return found + (deploy_alarms(ledger) if ledger else [])


# ID: 89cb7068-660d-4d10-b930-8ffc0acfd092
def deploy_alarms(ledger: Path) -> list[str]:
    """An alarm when the last deploy left the dev checkout behind. No ledger
    (no deploy yet) is no alarm; an unreadable one is."""
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except OSError as exc:
        return [f"CORE could not read its deploy ledger {ledger}: {exc}"]
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("action") != "deploy":
            continue
        moved = str(entry.get("dev_checkout") or "")
        if not moved.startswith("not moved") or moved == "not moved: not behind":
            return []  # moved, nothing to do, or ahead after a rollback
        return [
            "The dev checkout (`/opt/dev/CORE`) did not follow the last deploy "
            f"(`{str(entry.get('ref', ''))[:12]}`, {str(entry.get('at', ''))[:16]}): "
            f"{moved}. Anyone working in it reads old code; core-claude can "
            "see why in that deploy's output."
        ]
    return []
