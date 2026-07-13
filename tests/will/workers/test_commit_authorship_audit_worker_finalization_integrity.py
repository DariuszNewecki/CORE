"""Tests for CommitAuthorshipAuditWorker._audit_finalization_integrity
(ADR-148 D5, #763).

No real DB required — service_registry and ProposalSupervisionService are
mocked. Sibling to the authorship-integrity diff tests in
test_commit_authorship_audit_worker.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.commit_authorship_audit_worker import CommitAuthorshipAuditWorker


def _make_worker_instance() -> CommitAuthorshipAuditWorker:
    """Bypass Worker.__init__ (reads .intent/) — set minimal attributes by hand."""
    w = object.__new__(CommitAuthorshipAuditWorker)
    w._declaration = {}
    w._max_interval = 3600
    w.post_observation = AsyncMock()
    return w


def _row(proposal_id: str = "pid-1") -> dict[str, object]:
    return {
        "proposal_id": proposal_id,
        "execution_completed_at": None,
        "updated_at": None,
    }


async def test_audit_finalization_integrity_flags_new_violation() -> None:
    """A completed-without-consequence row not already open posts a finding
    and is counted as flagged."""
    worker = _make_worker_instance()

    blackboard_service = AsyncMock()
    blackboard_service.fetch_active_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )

    proposal_svc = AsyncMock()
    proposal_svc.fetch_completed_without_consequence = AsyncMock(
        return_value=[_row("pid-1")]
    )

    mock_registry = MagicMock()
    mock_registry.get_proposal_supervision_service = AsyncMock(
        return_value=proposal_svc
    )

    with patch(
        "body.services.service_registry.service_registry", mock_registry
    ):
        flagged, suppressed = await worker._audit_finalization_integrity(
            blackboard_service
        )

    assert flagged == 1
    assert suppressed == 0
    worker.post_observation.assert_awaited_once()
    call = worker.post_observation.await_args
    assert (
        call.kwargs["subject"]
        == "governance.proposal_finalization_integrity::pid-1"
    )
    assert call.kwargs["status"] == "indeterminate"
    assert call.kwargs["payload"]["proposal_id"] == "pid-1"
    assert call.kwargs["payload"]["grounding_adr"] == "ADR-148"


async def test_audit_finalization_integrity_suppresses_already_open() -> None:
    """A violation whose subject is already an open finding is not re-posted."""
    worker = _make_worker_instance()

    blackboard_service = AsyncMock()
    blackboard_service.fetch_active_finding_subjects_by_prefix = AsyncMock(
        return_value={"governance.proposal_finalization_integrity::pid-1"}
    )

    proposal_svc = AsyncMock()
    proposal_svc.fetch_completed_without_consequence = AsyncMock(
        return_value=[_row("pid-1")]
    )

    mock_registry = MagicMock()
    mock_registry.get_proposal_supervision_service = AsyncMock(
        return_value=proposal_svc
    )

    with patch(
        "body.services.service_registry.service_registry", mock_registry
    ):
        flagged, suppressed = await worker._audit_finalization_integrity(
            blackboard_service
        )

    assert flagged == 0
    assert suppressed == 1
    worker.post_observation.assert_not_awaited()


async def test_audit_finalization_integrity_no_violations() -> None:
    """No completed-without-consequence rows: nothing flagged, nothing posted."""
    worker = _make_worker_instance()

    blackboard_service = AsyncMock()
    blackboard_service.fetch_active_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )

    proposal_svc = AsyncMock()
    proposal_svc.fetch_completed_without_consequence = AsyncMock(return_value=[])

    mock_registry = MagicMock()
    mock_registry.get_proposal_supervision_service = AsyncMock(
        return_value=proposal_svc
    )

    with patch(
        "body.services.service_registry.service_registry", mock_registry
    ):
        flagged, suppressed = await worker._audit_finalization_integrity(
            blackboard_service
        )

    assert flagged == 0
    assert suppressed == 0
    worker.post_observation.assert_not_awaited()
