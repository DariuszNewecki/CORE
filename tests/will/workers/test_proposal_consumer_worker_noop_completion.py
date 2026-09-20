# tests/will/workers/test_proposal_consumer_worker_noop_completion.py
"""ProposalConsumerWorker.run() names a NOTHING_TO_COMMIT completion on the
board (ADR-104 D9 applied to the no-op loop, #901).

The executor revives the deferred findings of a no-op completion itself
and hands the revival back in ``findings_revival``; this Worker must post
that record (cap observations + ``proposal.noop.revival`` report — Worker
attribution per ``architecture.blackboard.worker_only_inserts``), count
the run as a no-op in its report, and still run the ordinary success
effects (the proposal did complete, ADR-148 D3). A completed proposal
without ``findings_revival`` must not touch the revival path at all.

Sibling of test_proposal_consumer_worker_lifecycle_gating.py; same harness.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.proposal_consumer_worker import ProposalConsumerWorker


def _make_worker_instance() -> ProposalConsumerWorker:
    w = object.__new__(ProposalConsumerWorker)
    w._declaration = {}
    w._max_interval = 300
    w._worker_uuid = uuid.uuid4()
    w._ctx = MagicMock()
    w.post_heartbeat = AsyncMock()
    w.post_report = AsyncMock()
    return w


def _result(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ok": True,
        "lifecycle_status": "completed",
        "actions_executed": 1,
        "actions_succeeded": 1,
        "actions_failed": 0,
        "duration_sec": 0.01,
        "action_results": {},
        "changed_files": [],
        "commit_outcome": "committed",
        "findings_revival": None,
        "error": None,
        "failure_reason": None,
    }
    base.update(overrides)
    return base


async def _run(worker: ProposalConsumerWorker, result: dict[str, object]) -> dict:
    worker._load_approved_proposals = AsyncMock(
        return_value=[{"proposal_id": "pid-1", "goal": "g"}]
    )
    executor_instance = MagicMock()
    executor_instance.execute = AsyncMock(return_value=result)
    with (
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor",
            return_value=executor_instance,
        ),
        patch(
            "will.workers.proposal_consumer_worker.apply_success_effects",
            new=AsyncMock(),
        ) as effects,
        patch(
            "will.workers.proposal_consumer_worker.revive_and_report",
            new=AsyncMock(),
        ) as revive,
        patch(
            "will.workers.proposal_consumer_worker.report_revival",
            new=AsyncMock(),
        ) as report,
        patch(
            "will.workers.proposal_consumer_worker.release_executing_proposals",
            new=AsyncMock(return_value=0),
        ),
    ):
        await worker.run()
    return {"effects": effects, "revive": revive, "report": report}


# ID: 0497e3ae-cad8-49f6-83bf-832549fc00ab
async def test_noop_completion_reports_revival_and_counts_no_op() -> None:
    worker = _make_worker_instance()
    revival = {"proposal_id": "pid-1", "revived_count": 1, "delegated_count": 1}
    mocks = await _run(
        worker,
        _result(commit_outcome="nothing_to_commit", findings_revival=revival),
    )

    mocks["report"].assert_awaited_once_with(
        worker, "pid-1", revival, report_subject_family="proposal.noop.revival"
    )
    mocks["revive"].assert_not_awaited()
    mocks["effects"].assert_awaited_once()
    payload = worker.post_report.await_args.kwargs["payload"]
    assert payload["succeeded"] == 1
    assert payload["no_op"] == 1
    assert payload["no_op_delegated"] == 1
    assert payload["failed"] == 0
    assert payload["results"][0]["commit_outcome"] == "nothing_to_commit"
    assert payload["results"][0]["findings_revived"] == 1
    assert payload["results"][0]["findings_delegated"] == 1


# ID: 6c609523-01a5-4cda-b2d4-d682b6c1dc17
async def test_real_completion_does_not_touch_the_revival_path() -> None:
    worker = _make_worker_instance()
    mocks = await _run(worker, _result())

    mocks["report"].assert_not_awaited()
    mocks["revive"].assert_not_awaited()
    mocks["effects"].assert_awaited_once()
    payload = worker.post_report.await_args.kwargs["payload"]
    assert payload["succeeded"] == 1
    assert payload["no_op"] == 0
    assert payload["no_op_delegated"] == 0
    assert payload["results"][0]["findings_delegated"] == 0
