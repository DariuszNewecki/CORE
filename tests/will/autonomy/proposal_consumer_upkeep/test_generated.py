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
