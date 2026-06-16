# src/api/v1/lane_routes.py

"""
Assisted Remediation Lane API endpoints (ADR-109 D1/D5, issue #652).

Surfaces the delegated-finding work queue over HTTP so the external-agent
contract (`core-admin lane`) can read what is waiting for human-gated
remediation. A delegated finding is one parked at `status=indeterminate`
with `resolution_mechanism=human` — the governor-inbox predicate.

This module is intentionally thin: it routes through the Will-layer
LaneService (API → Will), which delegates the blackboard read to Body. It
runs no ActionExecutor work. Per the settled gate-location decision (#652,
session 2026-06-16) the validation gate runs decoupled, CLI-side — never
inside an API handler — so the API surface stays read/DB-only.

CONSTITUTIONAL:
- No business logic and no Body bypass: the route routes through LaneService
  (Will), mirroring proposals_routes → ProposalService.
- LaneService is stateless and owns its own session lifecycle via the
  service_registry, so no get_api_session dependency is required.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from shared.logger import getLogger
from will.autonomy.lane_service import LaneService


logger = getLogger(__name__)


router = APIRouter(prefix="/lane")


@router.get(
    "",
    summary="List delegated findings (the assisted-lane work queue)",
    description=(
        "Return findings delegated for human-gated remediation — the "
        "Assisted Remediation Lane work queue. A delegated finding is one "
        "at `status=indeterminate` with `resolution_mechanism=human` "
        "(ADR-109). Ordered oldest-first; the `limit` query param caps the "
        "response size. The context-bundle exporter (#653) will enrich each "
        "entry later; for now the raw finding payload is returned."
    ),
)
# ID: 602fbaff-134e-413a-ab19-c8fb9f23aa53
async def list_delegated_findings(
    limit: int = Query(50, ge=1, description="Max delegated findings to return."),
) -> dict:
    """List delegated findings awaiting assisted remediation.

    Routes through LaneService (Will), which reads the canonical
    governor-inbox predicate. No action execution happens here — validation
    is decoupled and runs CLI-side (#652 gate-location decision).
    """
    findings = await LaneService().list_delegated_findings(limit=limit)
    return {
        "count": len(findings),
        "findings": findings,
    }
