# tests/will/workers/test_proposal_consumer_worker_test_delivery.py
"""ProposalConsumerWorker delivers CORE's generated tests every cycle
(body.infrastructure.delivery_branch). Without a token the tests wait and
ONE open finding says how many; once they travel it is resolved. Delivery
never stops proposal execution."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from body.infrastructure.delivery_branch import DeliveryOutcome
from will.workers.proposal_consumer_worker import ProposalConsumerWorker


def _worker() -> ProposalConsumerWorker:
    w = object.__new__(ProposalConsumerWorker)
    w._declaration = {}
    w._max_interval = 300
    w._worker_uuid = uuid.uuid4()
    w._ctx = MagicMock()
    w.post_report = AsyncMock()
    w.post_finding = AsyncMock()
    return w


async def _cycle(worker, outcome, open_rows):  # type: ignore[no-untyped-def]
    bb = MagicMock()
    bb.fetch_open_findings = AsyncMock(return_value=open_rows)
    bb.resolve_entries = AsyncMock()
    run = AsyncMock(return_value=outcome)
    if isinstance(outcome, BaseException):
        run = AsyncMock(side_effect=outcome)
    with (
        patch("body.infrastructure.delivery_branch.run_delivery", run),
        patch(
            "body.services.service_registry.service_registry.get_blackboard_service",
            new=AsyncMock(return_value=bb),
        ),
    ):
        await worker._deliver_tests()
    return bb


# ID: 8d3f1b6a-2e9c-4a57-b0d4-7c1e5a9f3b28
async def test_no_token_posts_one_waiting_finding_with_the_count() -> None:
    worker = _worker()
    waiting = DeliveryOutcome(
        "waiting",
        pending_commits=3,
        pending_files=2,
        reason="needs a GitHub token (CORE_GITHUB_TOKEN)",
    )
    await _cycle(worker, waiting, [])
    worker.post_finding.assert_awaited_once()
    kwargs = worker.post_finding.await_args.kwargs
    assert kwargs["subject"] == "test_delivery::waiting"
    assert kwargs["resolution_mechanism"] == "human"
    assert kwargs["payload"]["pending_commits"] == 3
    assert "3 generated test commit(s)" in kwargs["payload"]["message"]
    assert "token" in kwargs["payload"]["message"]

    again = _worker()
    await _cycle(again, waiting, [{"id": 4, "subject": "test_delivery::waiting"}])
    again.post_finding.assert_not_awaited()


# ID: 3a7e5c92-6f1b-4d84-a9e3-0b2d8f6c4a17
async def test_delivery_resolves_the_waiting_finding_and_reports() -> None:
    worker = _worker()
    bb = await _cycle(
        worker,
        DeliveryOutcome("delivered", 3, 2, pr_url="https://x/pull/9"),
        [{"id": 4, "subject": "test_delivery::waiting"}],
    )
    bb.resolve_entries.assert_awaited_once_with([4])
    assert worker.post_report.await_args.kwargs["payload"]["pr_url"] == (
        "https://x/pull/9"
    )


# ID: 5b9c2e4f-1a6d-4f38-8c7b-2e0a4d6f9b51
async def test_nothing_delivered_yet_touches_nothing_and_errors_never_raise() -> None:
    worker = _worker()
    bb = await _cycle(worker, DeliveryOutcome("none"), [])
    bb.fetch_open_findings.assert_not_awaited()
    worker.post_finding.assert_not_awaited()
    await _cycle(_worker(), RuntimeError("git exploded"), [])
