from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: 7b12ce84-a361-4c20-be09-7af3b56cc260
async def test_deliver_tests() -> None:
    from will.autonomy.proposal_consumer_upkeep import deliver_tests

    worker = MagicMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()

    ctx = MagicMock()

    outcome = MagicMock()
    outcome.state = "waiting"
    outcome.dropped = False
    outcome.pending_commits = 3
    outcome.reason = "no token"

    blackboard = MagicMock()
    blackboard.fetch_open_findings = AsyncMock(return_value=[{"id": "f1"}])
    blackboard.resolve_entries = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=blackboard)

    with (
        patch(
            "body.infrastructure.delivery_branch.run_delivery",
            new=AsyncMock(return_value=outcome),
        ),
        patch(
            "body.services.service_registry.service_registry",
            new=mock_registry,
        ),
    ):
        await deliver_tests(worker, ctx)

    blackboard.fetch_open_findings.assert_awaited_once()
    worker.post_report.assert_not_awaited()



import pytest


@pytest.mark.asyncio
# ID: 6becf0b6-a014-4248-b4f7-eede316b6759
async def test_sync_upstream():
    from will.autonomy.proposal_consumer_upkeep import sync_upstream

    outcome = MagicMock()
    outcome.state = "fast_forwarded"
    outcome.reason = None
    outcome.recovered = None
    outcome.from_sha = "abc123"
    outcome.to_sha = "def456"

    fake_repo_sync = MagicMock()
    fake_repo_sync.sync_if_free = MagicMock(return_value=outcome)

    blackboard = MagicMock()
    blackboard.fetch_open_findings = AsyncMock(return_value=[])
    blackboard.resolve_entries = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=blackboard)

    worker = MagicMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()

    ctx = MagicMock()

    with (
        patch(
            "body.infrastructure.repo_sync.repo_sync_for",
            return_value=fake_repo_sync,
        ),
        patch(
            "body.infrastructure.repo_sync.SyncRecoveryRefused",
            Exception,
        ),
        patch(
            "body.services.service_registry.service_registry",
            mock_registry,
        ),
    ):
        await sync_upstream(worker, ctx)

    worker.post_finding.assert_not_called()
    blackboard.resolve_entries.assert_not_called()
    worker.post_report.assert_awaited_once()
    _args, kwargs = worker.post_report.call_args
    assert kwargs["subject"] == "proposal_consumer_worker.repo_sync"
    assert kwargs["payload"]["state"] == "fast_forwarded"
    assert kwargs["payload"]["from"] == "abc123"
    assert kwargs["payload"]["to"] == "def456"
