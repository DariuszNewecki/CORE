# src/shared/protocols/blackboard_poster.py
"""
The Worker's blackboard posting surface, declared once.

Helpers that post on a Worker's behalf (remediation ceremony, goal-run records)
depend on a narrow slice of ``Worker`` rather than on the class itself. Those
slices used to re-declare the same method stubs in each module; they extend
these protocols instead.

CONSTITUTIONAL: shared protocol only — no I/O, no imports of mind/, body/, will/.
"""

from __future__ import annotations

from typing import Any, Protocol


# ID: 476b9a3c-a899-4e2f-9f2c-267cdbc42265
class ReportPoster(Protocol):
    """Anything that can post a report to the blackboard (``Worker.post_report``)."""

    # ID: 6eab820c-bb13-4e43-8a7e-a1673bde1389
    async def post_report(self, subject: str, payload: dict[str, Any]) -> Any:
        """Post a report under ``subject``."""
        ...


# ID: bd233053-5aa4-4e98-b9f9-3637794ceeca
class ObservationPoster(ReportPoster, Protocol):
    """A report poster that can also post a status-bearing observation."""

    # ID: a3bb4365-3dd0-4081-8dd6-14cdcebde169
    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> Any:
        """Post an observation under ``subject`` with the given status."""
        ...
