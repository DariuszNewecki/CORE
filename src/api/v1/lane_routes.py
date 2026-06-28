# src/api/v1/lane_routes.py

"""
Assisted Remediation Lane API endpoints (ADR-109 D1/D5, issue #652).

Surfaces the delegated-finding work queue over HTTP so the external-agent
contract (`core-admin lane`) can read what is waiting for human-gated
remediation. A delegated finding is one parked at `status=indeterminate`
with `resolution_mechanism=human` — the governor-inbox predicate.

This module is intentionally thin: it routes through the Will-layer
LaneService (API → Will), which delegates blackboard reads/writes to Body. It
runs no ActionExecutor work. Per the settled gate-location decision (#652) the
validation gate runs decoupled — the agent dispatches `assisted.validate_diff`
through the general action-run surface (`POST /fix/run/{fix_id}`), never inside
a lane handler — so this surface stays read/DB-only. `propose` is a DB-only
write: it re-reads the persisted validation verdict from `core.fix_runs`
(a sanctioned read, mirroring `GET /fix/runs/{id}`) and delegates proposal
creation + finding deferral to LaneService.

CONSTITUTIONAL:
- No business logic and no Body bypass: the route routes through LaneService
  (Will), mirroring proposals_routes → ProposalService.
- The propose handler's only direct DB touch is the sanctioned `get_api_session`
  read of the validation verdict; all writes happen in Will/Body.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session
from shared.logger import getLogger
from will.autonomy.lane_service import LaneProposeError, LaneService


logger = getLogger(__name__)


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/lane")

_VALIDATE_ACTION = "assisted.validate_diff"


# ID: 4604947c-4684-4e00-aa14-e37acdf8da67
class ProposeRequest(BaseModel):
    """Body for `POST /lane/{finding_id}/propose`.

    The agent-authored unified diff plus the id of the `assisted.validate_diff`
    run that already cleared it (an `assisted.validate_diff` action dispatched
    via `POST /fix/run/{fix_id}`, tracked in `core.fix_runs`). The endpoint
    re-reads that run's persisted verdict — it never trusts the caller's word
    that validation passed.
    """

    patch: str
    validation_run_id: str


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


@router.get(
    "/next",
    summary="Pull the next delegated finding (FIFO head)",
    description=(
        "Return the oldest delegated finding — the lane's 'pull next work' "
        "surface — or 404 if the lane is empty. The rich context bundle (#653) "
        "will enrich this later; for now the raw finding is returned. Declared "
        "before /{finding_id} so 'next' is not captured as an id."
    ),
)
# ID: 4480959b-2563-4b04-94bc-35fab10b67e4
async def next_delegated_finding() -> dict:
    """Return the oldest delegated finding, or 404 if the lane is empty."""
    finding = await LaneService().next_delegated_finding()
    if finding is None:
        raise HTTPException(status_code=404, detail="Lane is empty.")
    return finding


@router.get(
    "/{finding_id}",
    summary="Get a single delegated finding with its context bundle",
    description=(
        "Return one delegated finding by id (same governor-inbox predicate as "
        "the list) enriched with the #653 context bundle — rule rationale, "
        "whether the rule is still in the active registry, and the "
        "remediation-map guidance. 404 if it is not a live lane item — already "
        "worked, resolved, or never delegated."
    ),
)
# ID: 22240f3e-72c0-433f-8f93-e29cb3462f82
async def get_delegated_finding(
    finding_id: str = Path(..., description="Blackboard finding id (uuid)."),
) -> dict:
    """Return a single delegated finding + bundle, or 404 if not a live lane item."""
    finding = await LaneService().get_finding_bundle(finding_id)
    if finding is None:
        raise HTTPException(
            status_code=404,
            detail=f"Not a live delegated lane item: {finding_id}",
        )
    return finding


@router.post(
    "/{finding_id}/claim",
    summary="Mark a delegated finding as being worked",
    description=(
        "Stamp a delegated finding as in-progress by an external agent (ADR-109 "
        "§2). Claiming does not change the finding's status — it stays a live "
        "lane item — it only records who is working it so it is visibly tracked, "
        "not parked. 404 if it is not a live lane item."
    ),
)
# ID: 501609c9-9d61-454f-b452-a48463e2978c
async def claim_delegated_finding(
    finding_id: str = Path(..., description="Delegated finding id (uuid)."),
    agent: str = Query(..., description="Identity of the working agent."),
) -> dict:
    """Mark a delegated finding as being worked; 404 if not a live lane item."""
    claimed = await LaneService().claim_delegated_finding(finding_id, agent)
    if not claimed:
        raise HTTPException(
            status_code=404,
            detail=f"Not a live delegated lane item: {finding_id}",
        )
    return {"finding_id": finding_id, "claimed_by": agent, "status": "indeterminate"}


@router.post(
    "/{finding_id}/propose",
    status_code=201,
    summary="Ingest a validated agent diff as a human-gated proposal",
    description=(
        "Create a human-gated multi-file proposal from an agent-authored diff "
        "that has already cleared `assisted.validate_diff` (ADR-109 D3/D4). "
        "This endpoint is DB-only: it re-reads the persisted verdict of the "
        "named validation run from `core.fix_runs` (it never trusts the "
        "caller's claim that validation passed), confirms the submitted patch "
        "matches the bytes that were validated, then routes proposal creation "
        "and finding deferral through the Will-layer LaneService. The existing "
        "`proposals approve`/`execute` path drives the rest."
    ),
)
# ID: fb52b378-96eb-41fb-a834-127f992e75a0
async def propose_diff(
    finding_id: str = Path(..., description="Delegated finding id (uuid)."),
    body: ProposeRequest = Body(...),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Ingest a validated diff as a governed, human-gated proposal.

    The validation gate is the auto-firing oracle: the recorded verdict — not
    the caller — decides whether the diff is approvable. The proposal's own
    approval gate (#654) re-checks the recorded result before the governor can
    approve.
    """
    # 1. Recover the persisted verdict of the named validation run. Sanctioned
    #    DB read (mirrors GET /fix/runs/{id}); no action re-execution here.
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT fix_id, status, result
                  FROM core.fix_runs
                 WHERE id = cast(:rid as uuid)
                """
                ),
                {"rid": body.validation_run_id},
            )
        )
        .mappings()
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown validation run: {body.validation_run_id}",
        )
    if row["fix_id"] != _VALIDATE_ACTION:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Run {body.validation_run_id} is not an {_VALIDATE_ACTION} "
                f"run (was {row['fix_id']!r})."
            ),
        )

    result = row["result"] or {}
    data = result.get("data") or {}
    if row["status"] != "completed" or not result.get("ok"):
        raise HTTPException(
            status_code=422,
            detail="Validation did not pass; diff is not approvable. Re-fetch the lane run for full validation results.",
        )

    # 2. Bind the verdict to the exact bytes that were validated — an agent who
    #    edits the diff after validating cannot ride a stale PASS (ADR-109 §4).
    submitted_sha = hashlib.sha256(body.patch.encode("utf-8")).hexdigest()
    if data.get("patch_sha256") != submitted_sha:
        raise HTTPException(
            status_code=422,
            detail=(
                "Submitted patch does not match the validated diff; "
                "re-run validation on the current patch."
            ),
        )

    production_set = data.get("production_set") or []

    # 3. Orchestrate creation + deferral in Will (no DB writes in the handler).
    try:
        proposal_id = await LaneService().propose_validated_diff(
            finding_id=finding_id,
            patch=body.patch,
            production_set=production_set,
        )
    except LaneProposeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "proposal_id": proposal_id,
        "status": "draft",
        "approval_required": True,
        "scope_files": production_set,
    }
