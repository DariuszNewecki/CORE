# tests/will/workers/test_proposal_consumer_worker_lifecycle_gating.py
"""ProposalConsumerWorker.run() gating on lifecycle_status, not `ok` (#812).

Prior to #812, this worker branched on ProposalExecutor.execute()'s bare
`ok` flag, which stayed True for a proposal left FINALIZING (commit
succeeded, consequence chain never became durable) — so a proposal that
never reached ADR-148's COMPLETED proof state was counted as succeeded and
had apply_success_effects run for it (real blackboard findings posted for
work that wasn't durably done). These tests drive run() end-to-end with
ProposalExecutor.execute mocked to return each of the three
lifecycle_status values and assert the counters/effects/revival calls
route correctly for each.

No real DB or blackboard — post_heartbeat/post_report/_load_approved_
proposals are mocked directly on the instance; ProposalExecutor,
apply_success_effects, revive_and_report, release_executing_proposals are
patched at their import site in the module under test.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.proposal_consumer_worker import ProposalConsumerWorker


def _make_worker_instance() -> ProposalConsumerWorker:
    """Bypass Worker.__init__ (reads .intent/) — set minimal attributes by hand."""
    w = object.__new__(ProposalConsumerWorker)
    w._declaration = {}
    w._max_interval = 300
    w._worker_uuid = uuid.uuid4()
    w._ctx = MagicMock()
    w.post_heartbeat = AsyncMock()
    w.post_report = AsyncMock()
    return w


def _proposal(proposal_id: str = "pid-1") -> dict[str, object]:
    return {"proposal_id": proposal_id, "goal": "test goal"}


def _result(lifecycle_status: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ok": lifecycle_status == "completed",
        "lifecycle_status": lifecycle_status,
        "actions_executed": 1,
        "actions_succeeded": 1 if lifecycle_status == "completed" else 0,
        "actions_failed": 0,
        "duration_sec": 0.01,
        "action_results": {},
        "error": None,
        "failure_reason": None,
    }
    base.update(overrides)
    return base


async def test_completed_counts_succeeded_and_runs_success_effects() -> None:
    worker = _make_worker_instance()
    worker._load_approved_proposals = AsyncMock(return_value=[_proposal()])

    executor_instance = MagicMock()
    executor_instance.execute = AsyncMock(return_value=_result("completed"))

    with (
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor",
            return_value=executor_instance,
        ),
        patch(
            "will.workers.proposal_consumer_worker.apply_success_effects",
            new=AsyncMock(),
        ) as effects_mock,
        patch(
            "will.workers.proposal_consumer_worker.revive_and_report",
            new=AsyncMock(),
        ) as revive_mock,
        patch(
            "will.workers.proposal_consumer_worker.release_executing_proposals",
            new=AsyncMock(return_value=0),
        ),
    ):
        await worker.run()

    effects_mock.assert_awaited_once()
    revive_mock.assert_not_awaited()
    payload = worker.post_report.await_args.kwargs["payload"]
    assert payload["succeeded"] == 1
    assert payload["failed"] == 0
    assert payload["pending"] == 0


async def test_finalizing_counts_pending_and_does_not_revive_or_run_effects() -> None:
    """The core #812 regression test: a proposal left FINALIZING must be
    neither counted as succeeded (no success effects) nor treated as
    failed (no revival — the ADR-148 D4 reaper owns re-driving it, and
    reviving deferred findings here would race that ownership)."""
    worker = _make_worker_instance()
    worker._load_approved_proposals = AsyncMock(return_value=[_proposal()])

    executor_instance = MagicMock()
    executor_instance.execute = AsyncMock(return_value=_result("finalizing"))

    with (
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor",
            return_value=executor_instance,
        ),
        patch(
            "will.workers.proposal_consumer_worker.apply_success_effects",
            new=AsyncMock(),
        ) as effects_mock,
        patch(
            "will.workers.proposal_consumer_worker.revive_and_report",
            new=AsyncMock(),
        ) as revive_mock,
        patch(
            "will.workers.proposal_consumer_worker.release_executing_proposals",
            new=AsyncMock(return_value=0),
        ),
    ):
        await worker.run()

    effects_mock.assert_not_awaited()
    revive_mock.assert_not_awaited()
    payload = worker.post_report.await_args.kwargs["payload"]
    assert payload["succeeded"] == 0
    assert payload["failed"] == 0
    assert payload["pending"] == 1


async def test_failed_counts_failed_and_revives_findings() -> None:
    worker = _make_worker_instance()
    worker._load_approved_proposals = AsyncMock(return_value=[_proposal()])

    executor_instance = MagicMock()
    executor_instance.execute = AsyncMock(
        return_value=_result("failed", ok=False, failure_reason="boom")
    )

    with (
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor",
            return_value=executor_instance,
        ),
        patch(
            "will.workers.proposal_consumer_worker.apply_success_effects",
            new=AsyncMock(),
        ) as effects_mock,
        patch(
            "will.workers.proposal_consumer_worker.revive_and_report",
            new=AsyncMock(),
        ) as revive_mock,
        patch(
            "will.workers.proposal_consumer_worker.release_executing_proposals",
            new=AsyncMock(return_value=0),
        ),
    ):
        await worker.run()

    effects_mock.assert_not_awaited()
    revive_mock.assert_awaited_once()
    payload = worker.post_report.await_args.kwargs["payload"]
    assert payload["succeeded"] == 0
    assert payload["failed"] == 1
    assert payload["pending"] == 0


async def test_missing_lifecycle_status_fails_closed_not_succeeded() -> None:
    """A result dict missing lifecycle_status entirely (e.g. an
    unanticipated code path) must never be treated as a success — fail
    closed to the failed/revival branch, not the success-effects branch."""
    worker = _make_worker_instance()
    worker._load_approved_proposals = AsyncMock(return_value=[_proposal()])

    executor_instance = MagicMock()
    result_without_status = _result("completed")
    del result_without_status["lifecycle_status"]
    executor_instance.execute = AsyncMock(return_value=result_without_status)

    with (
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor",
            return_value=executor_instance,
        ),
        patch(
            "will.workers.proposal_consumer_worker.apply_success_effects",
            new=AsyncMock(),
        ) as effects_mock,
        patch(
            "will.workers.proposal_consumer_worker.revive_and_report",
            new=AsyncMock(),
        ) as revive_mock,
        patch(
            "will.workers.proposal_consumer_worker.release_executing_proposals",
            new=AsyncMock(return_value=0),
        ),
    ):
        await worker.run()

    effects_mock.assert_not_awaited()
    revive_mock.assert_awaited_once()
