# src/api/v1/thesis_routes.py
"""
Thesis API (.specs/DECISIONS.md, "Thesis and baselines (2026-10-13)").

``GET /v1/thesis``: the thesis sensor's latest daily report — the four
numbers, the governor's line, the breaches and the sources it could not
read. Read-only; the report comes through api.dependencies, no Body import
here (architecture.api.no_body_bypass).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.dependencies import ThesisLatestDep


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/thesis")


# ID: 84c21d51-5976-4734-8bb9-15184c02cd2c
class ThesisResponse(BaseModel):
    """One day's thesis measures."""

    day: str
    line: str
    unverified_writes: int | None = None
    ai_share: float | None = None
    waste_per_change: float | None = None
    convergence: float | None = None
    breaches: list[dict[str, Any]] = []
    unavailable: list[str] = []


@router.get(
    "",
    response_model=ThesisResponse,
    summary="Latest thesis measures",
    description=(
        "The thesis sensor's latest daily report: unverified writes to main, "
        "AI authorship, waste trips per merged change and finding "
        "convergence, with the rules they broke. 404 before the first "
        "measurement."
    ),
)
# ID: 12e31bda-ccb1-44e9-899d-5dc0ce41a1da
async def get_thesis(latest: ThesisLatestDep) -> dict[str, Any]:
    """Return the latest daily thesis report."""
    if latest is None:
        raise HTTPException(status_code=404, detail="The thesis is not measured yet.")
    return latest
