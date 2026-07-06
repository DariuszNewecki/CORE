# tests/will/workers/test_proposal_consumer_revival_cap.py
"""
Tests for the remediation-cap observation in revive_and_report
(proposal_consumer_revival.py).

Verifies that blackboard.remediation_cap_reached observations use the
original finding's subject (stable per violation class) rather than the
entry UUID, so the same capped violation does not generate a new F-19
subject on every proposal failure cycle.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


_PROPOSAL_ID = "prop-cap-0001"
_ENTRY_ID_1 = "aaaaaaaa-1111-2222-3333-444444444444"
_ENTRY_ID_2 = "bbbbbbbb-5555-6666-7777-888888888888"
_FINDING_SUBJECT_1 = "audit.violation::purity.no_orphan_files::src/shared/foo.py"
_FINDING_SUBJECT_2 = "audit.violation::purity.no_orphan_files::src/shared/bar.py"


def _make_worker() -> MagicMock:
    worker = MagicMock()
    worker.post_observation = AsyncMock()
    worker.post_report = AsyncMock()
    return worker


def _make_revival_result(
    abandoned_ids: list[str],
    abandoned_subjects: list[str],
    revived_count: int = 0,
) -> dict:
    return {
        "proposal_id": _PROPOSAL_ID,
        "failure_reason": "executor_failed",
        "revived_count": revived_count,
        "revived_finding_ids": [],
        "revived_subjects": [],
        "abandoned_count": len(abandoned_ids),
        "abandoned_finding_ids": abandoned_ids,
        "abandoned_subjects": abandoned_subjects,
    }


def _make_bb_service(revival_result) -> MagicMock:
    svc = MagicMock()
    svc.revive_findings_for_failed_proposal = AsyncMock(return_value=revival_result)
    return svc


def _make_registry(bb_service) -> MagicMock:
    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb_service)
    return registry


async def test_cap_reached_subject_uses_finding_subject_not_entry_id() -> None:
    """
    The cap_reached observation subject must be
    blackboard.remediation_cap_reached::<finding_subject>, not
    blackboard.remediation_cap_reached::<entry_id>.

    Regression guard: entry_id is a UUID that changes when a finding is
    revived; using it as the subject creates a new F-19 subject on every
    failure cycle, flooding the convergence metric.
    """
    from will.workers.proposal_consumer_revival import revive_and_report

    revival = _make_revival_result(
        abandoned_ids=[_ENTRY_ID_1],
        abandoned_subjects=[_FINDING_SUBJECT_1],
    )
    bb_service = _make_bb_service(revival)
    registry = _make_registry(bb_service)
    worker = _make_worker()

    with (
        patch("body.services.service_registry.service_registry", registry),
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=3)),
        ),
    ):
        await revive_and_report(worker, _PROPOSAL_ID, "executor_failed")

    worker.post_observation.assert_awaited_once()
    call_kwargs = worker.post_observation.await_args.kwargs
    subject = call_kwargs["subject"]

    assert subject == f"blackboard.remediation_cap_reached::{_FINDING_SUBJECT_1}", (
        f"Subject must use finding_subject, got: {subject}"
    )
    assert _ENTRY_ID_1 not in subject, (
        "Subject must NOT contain the entry UUID (unstable per cycle)"
    )
    assert call_kwargs["payload"]["entry_id"] == _ENTRY_ID_1
    assert call_kwargs["payload"]["finding_subject"] == _FINDING_SUBJECT_1


async def test_cap_reached_posts_one_observation_per_abandoned_finding() -> None:
    """Two abandoned findings → two stable, distinct observations."""
    from will.workers.proposal_consumer_revival import revive_and_report

    revival = _make_revival_result(
        abandoned_ids=[_ENTRY_ID_1, _ENTRY_ID_2],
        abandoned_subjects=[_FINDING_SUBJECT_1, _FINDING_SUBJECT_2],
    )
    bb_service = _make_bb_service(revival)
    registry = _make_registry(bb_service)
    worker = _make_worker()

    with (
        patch("body.services.service_registry.service_registry", registry),
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=3)),
        ),
    ):
        await revive_and_report(worker, _PROPOSAL_ID, "executor_failed")

    assert worker.post_observation.await_count == 2
    subjects = [
        call.kwargs["subject"]
        for call in worker.post_observation.await_args_list
    ]
    assert subjects[0] == f"blackboard.remediation_cap_reached::{_FINDING_SUBJECT_1}"
    assert subjects[1] == f"blackboard.remediation_cap_reached::{_FINDING_SUBJECT_2}"


async def test_no_abandoned_findings_posts_nothing() -> None:
    """If the revival has no abandoned findings, no observation is posted."""
    from will.workers.proposal_consumer_revival import revive_and_report

    revival = _make_revival_result(
        abandoned_ids=[],
        abandoned_subjects=[],
        revived_count=2,
    )
    bb_service = _make_bb_service(revival)
    registry = _make_registry(bb_service)
    worker = _make_worker()

    with (
        patch("body.services.service_registry.service_registry", registry),
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=3)),
        ),
    ):
        await revive_and_report(worker, _PROPOSAL_ID, "executor_failed")

    worker.post_observation.assert_not_awaited()
    worker.post_report.assert_awaited_once()
