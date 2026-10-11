# tests/will/workers/test_proposal_consumer_worker_repo_sync.py
"""ProposalConsumerWorker and CORE's clone (ADR-132 D10 · D2, C3).

- A sync that cannot proceed is ONE open finding for the governor, resolved
  once a later sync succeeds.
- A proposal the executor refuses as blocked (GovernanceInstrumentError: the
  repo lock, a broken vocabulary projection) stays approved — never marked
  failed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from body.infrastructure.repo_sync import SyncOutcome, SyncRecoveryRefused
from shared.exceptions import GovernanceInstrumentError
from will.workers.proposal_consumer_worker import ProposalConsumerWorker


def _worker() -> ProposalConsumerWorker:
    w = object.__new__(ProposalConsumerWorker)
    w._declaration = {}
    w._max_interval = 300
    w._worker_uuid = uuid.uuid4()
    w._ctx = MagicMock()
    w.post_heartbeat = AsyncMock()
    w.post_report = AsyncMock()
    w.post_finding = AsyncMock()
    return w


def _blackboard(open_rows: list[dict[str, object]]) -> MagicMock:
    bb = MagicMock()
    bb.fetch_open_findings = AsyncMock(return_value=open_rows)
    bb.resolve_entries = AsyncMock()
    return bb


async def _sync(worker: ProposalConsumerWorker, outcome, bb: MagicMock) -> None:
    sync = MagicMock()
    if isinstance(outcome, BaseException):
        sync.sync_if_free = MagicMock(side_effect=outcome)
    else:
        sync.sync_if_free = MagicMock(return_value=outcome)
    with (
        patch("body.infrastructure.repo_sync.repo_sync_for", return_value=sync),
        patch(
            "body.services.service_registry.service_registry.get_blackboard_service",
            new=AsyncMock(return_value=bb),
        ),
    ):
        await worker._sync_upstream()


# ID: 5e99f437-fd7a-4070-a812-02d0dcba4305
async def test_divergence_posts_one_human_finding() -> None:
    worker, bb = _worker(), _blackboard([])
    await _sync(worker, SyncOutcome("diverged", "a" * 40, "b" * 40, "diverged"), bb)
    worker.post_finding.assert_awaited_once()
    kwargs = worker.post_finding.await_args.kwargs
    assert kwargs["subject"] == "repo_sync::clone"
    assert kwargs["resolution_mechanism"] == "human"
    assert kwargs["payload"]["state"] == "diverged"


# ID: 61e3a6c7-073c-405c-a6bb-09908ee35443
async def test_an_open_finding_is_not_posted_again() -> None:
    worker, bb = _worker(), _blackboard([{"id": 1, "subject": "repo_sync::clone"}])
    await _sync(worker, SyncOutcome("failed", reason="network"), bb)
    worker.post_finding.assert_not_awaited()


# ID: a891a623-048b-437c-8639-59546e6208a9
async def test_refused_recovery_is_a_finding() -> None:
    worker, bb = _worker(), _blackboard([])
    await _sync(worker, SyncRecoveryRefused("HEAD at neither end"), bb)
    assert worker.post_finding.await_args.kwargs["payload"]["state"] == (
        "recovery_refused"
    )


# ID: 5fe9df5d-d200-4859-827b-5d00ea905347
async def test_success_resolves_the_open_finding_and_reports() -> None:
    worker, bb = _worker(), _blackboard([{"id": 7, "subject": "repo_sync::clone"}])
    await _sync(worker, SyncOutcome("fast_forwarded", "a" * 40, "b" * 40), bb)
    bb.resolve_entries.assert_awaited_once_with([7])
    worker.post_finding.assert_not_awaited()
    assert worker.post_report.await_args.kwargs["payload"]["state"] == (
        "fast_forwarded"
    )


# ID: d92f8f1f-4176-4b0f-b404-b0dbc1881568
async def test_disabled_and_busy_touch_nothing() -> None:
    for state in ("disabled", "busy"):
        worker, bb = _worker(), _blackboard([])
        await _sync(worker, SyncOutcome(state), bb)  # type: ignore[arg-type]
        bb.fetch_open_findings.assert_not_awaited()
        worker.post_finding.assert_not_awaited()


# ID: d4f6bb91-d623-477e-9f3a-eb49abca2609
async def test_blocked_proposal_stays_approved() -> None:
    worker = _worker()
    worker._sync_upstream = AsyncMock()
    worker._load_approved_proposals = AsyncMock(
        return_value=[{"proposal_id": "pid-1", "goal": "g"}]
    )
    executor = MagicMock()
    executor.execute = AsyncMock(
        side_effect=GovernanceInstrumentError("repo_lock", "held")
    )
    with (
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor", return_value=executor
        ),
        patch(
            "will.workers.proposal_consumer_worker.mark_proposal_failed",
            new=AsyncMock(),
        ) as mark_failed,
        patch(
            "will.workers.proposal_consumer_worker.revive_and_report",
            new=AsyncMock(),
        ) as revive,
        patch(
            "will.workers.proposal_consumer_worker.release_executing_proposals",
            new=AsyncMock(return_value=0),
        ),
    ):
        await worker.run()
    mark_failed.assert_not_awaited()
    revive.assert_not_awaited()
    payload = worker.post_report.await_args.kwargs["payload"]
    assert payload["failed"] == 0
    assert payload["pending"] == 1
