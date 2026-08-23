# tests/api/v1/test_lane_routes.py

"""Unit tests for lane_routes — Assisted Remediation Lane (ADR-109 #652).

Covers GET /lane (list delegated findings). Mocks the Will-layer
LaneService the route routes through; the route runs no action and owns no
session — ADR-154 D2 moved the former inline `core.fix_runs` re-read out of
this module entirely, into the Body-owned trusted validation service reached
via LaneService. `propose` tests here only cover the route's job: call
LaneService and map its outcome (success, CandidateConstructionError,
LaneProposeError) to the right HTTP response. The privileged-verification
behavior itself is covered by
`tests/body/services/test_validated_candidate_service.py`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from api.v1.lane_routes import (
    ProposeRequest,
    claim_delegated_finding,
    list_delegated_findings,
    next_delegated_finding,
    propose_diff,
)
from shared.models.validated_remediation_candidate import CandidateConstructionError
from will.autonomy.lane_service import LaneProposeError


def _mk_finding(fid: str = "f-1") -> dict:
    return {
        "id": fid,
        "subject": "purity.no_orphan_files::src/x.py",
        "payload": {"rule": "purity.no_orphan_files"},
        "created_at": "2026-06-16T07:00:00",
    }


_PATCH = "--- a/src/x.py\n+++ b/src/x.py\n"


async def test_list_delegated_wraps_findings_in_count_envelope():
    """The route delegates to LaneService.list_delegated_findings and wraps
    the result in {count, findings}, forwarding the limit."""
    service = AsyncMock()
    service.list_delegated_findings = AsyncMock(return_value=[_mk_finding()])

    with patch("api.v1.lane_routes.LaneService", return_value=service):
        out = await list_delegated_findings(limit=25)

    assert out["count"] == 1
    assert out["findings"] == [_mk_finding()]
    service.list_delegated_findings.assert_awaited_once_with(limit=25)


async def test_list_delegated_empty_returns_zero_count():
    """An empty lane returns count=0 and an empty list, not an error."""
    service = AsyncMock()
    service.list_delegated_findings = AsyncMock(return_value=[])

    with patch("api.v1.lane_routes.LaneService", return_value=service):
        out = await list_delegated_findings(limit=50)

    assert out == {"count": 0, "findings": []}


# --- propose: outcome mapping (verification itself lives in Body — ADR-154 D2) ---


async def test_propose_rejects_candidate_construction_error():
    """Any ADR-154 D2 precondition failure on the named validation run
    (unknown run, wrong action, failed run, patch mismatch, missing base
    SHA — see test_validated_candidate_service.py for each) surfaces from
    LaneService as CandidateConstructionError; the route maps it to 422 and
    creates nothing."""
    body = ProposeRequest(patch=_PATCH, validation_run_id="missing")
    service = AsyncMock()
    service.propose_validated_diff = AsyncMock(
        side_effect=CandidateConstructionError("Unknown validation run: missing")
    )

    with patch("api.v1.lane_routes.LaneService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await propose_diff(finding_id="f-1", body=body)

    assert exc.value.status_code == 422
    assert "Unknown validation run" in exc.value.detail


async def test_propose_rejects_finding_not_live():
    """A finding that is no longer a live delegated lane item surfaces as
    LaneProposeError; the route maps it to 409."""
    body = ProposeRequest(patch=_PATCH, validation_run_id="run-1")
    service = AsyncMock()
    service.propose_validated_diff = AsyncMock(
        side_effect=LaneProposeError("Finding 'f-1' is not a live delegated lane item")
    )

    with patch("api.v1.lane_routes.LaneService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await propose_diff(finding_id="f-1", body=body)

    assert exc.value.status_code == 409


async def test_propose_happy_path_creates_proposal():
    """A LaneService success routes back through as the draft proposal
    envelope with the production set LaneService (via the candidate)
    reported — the route asserts nothing about validation itself."""
    body = ProposeRequest(patch=_PATCH, validation_run_id="run-1")
    service = AsyncMock()
    service.propose_validated_diff = AsyncMock(
        return_value=("prop-xyz", ["src/x.py", "src/base.py"])
    )

    with patch("api.v1.lane_routes.LaneService", return_value=service):
        out = await propose_diff(finding_id="f-1", body=body)

    assert out == {
        "proposal_id": "prop-xyz",
        "status": "draft",
        "approval_required": True,
        "scope_files": ["src/x.py", "src/base.py"],
    }
    service.propose_validated_diff.assert_awaited_once_with(
        finding_id="f-1",
        patch=_PATCH,
        validation_run_id="run-1",
    )


# --- next / claim -------------------------------------------------------------


async def test_next_returns_head():
    """next surfaces the FIFO head finding verbatim."""
    service = AsyncMock()
    service.next_delegated_finding = AsyncMock(return_value=_mk_finding())
    with patch("api.v1.lane_routes.LaneService", return_value=service):
        out = await next_delegated_finding()
    assert out == _mk_finding()


async def test_next_404_when_lane_empty():
    """An empty lane is a 404, not a null body."""
    service = AsyncMock()
    service.next_delegated_finding = AsyncMock(return_value=None)
    with patch("api.v1.lane_routes.LaneService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await next_delegated_finding()
    assert exc.value.status_code == 404


async def test_claim_success_returns_envelope():
    """A claimed live finding returns the claim envelope (status unchanged)."""
    service = AsyncMock()
    service.claim_delegated_finding = AsyncMock(return_value=True)
    with patch("api.v1.lane_routes.LaneService", return_value=service):
        out = await claim_delegated_finding(finding_id="f-1", agent="claude-code")
    assert out == {
        "finding_id": "f-1",
        "claimed_by": "claude-code",
        "status": "indeterminate",
    }
    service.claim_delegated_finding.assert_awaited_once_with("f-1", "claude-code")


async def test_claim_404_when_not_live():
    """Claiming a non-live lane item is a 404."""
    service = AsyncMock()
    service.claim_delegated_finding = AsyncMock(return_value=False)
    with patch("api.v1.lane_routes.LaneService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await claim_delegated_finding(finding_id="gone", agent="x")
    assert exc.value.status_code == 404


def test_mutation_routes_carry_governor_gate():
    """#808/#770: claim stamps claimed_by on a live finding row;
    propose creates a governed Proposal and defers the finding to it.
    Both are real mutations -- governor-gated."""
    from api.dependencies import require_governor
    from api.v1.lane_routes import router

    gated_by_route = {
        (method, route.path): require_governor in route.dependencies
        for route in router.routes
        for method in route.methods
    }
    assert gated_by_route[("POST", "/lane/{finding_id}/claim")] is True
    assert gated_by_route[("POST", "/lane/{finding_id}/propose")] is True
