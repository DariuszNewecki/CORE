"""Tests for BlackboardShopManager.

2026-06-07 (#572 Cat B batch 19): converted from unittest.TestCase
``setUp`` to a pytest fixture. The autogen vintage relied on the
unittest setUp lifecycle, which our direct-invocation probe runner
doesn't honour (pytest itself would, but the test was clearly a
single-instance shape better expressed as a fixture). One smoke test
preserved.
"""

from __future__ import annotations

import pytest

from will.workers.blackboard_shop_manager import BlackboardShopManager


@pytest.fixture
# ID: 6729effb-49c2-4179-b445-a942536a270d
def shop_manager() -> BlackboardShopManager:
    return BlackboardShopManager()


# ID: 1edda2ff-ad6c-46b5-aa0a-22dcd5cb51cd
def test_initialization(shop_manager: BlackboardShopManager) -> None:
    """BlackboardShopManager instantiates with no args and is an instance
    of its own class — the basic import + construction smoke check."""
    assert isinstance(shop_manager, BlackboardShopManager)


from unittest.mock import AsyncMock, MagicMock, patch


# ID: f541bc32-0a01-441d-8a07-fd4c0b7223fb
def test_BlackboardShopManager_run() -> None:
    worker = BlackboardShopManager()

    worker.post_heartbeat = AsyncMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()

    worker._sweep_resolved_stale_alerts = AsyncMock(return_value=0)
    worker._sweep_telemetry_keep_last_n = AsyncMock(return_value=0)
    worker._sweep_delegate_findings_ttl = AsyncMock(return_value=0)
    worker._sweep_orphaned_claims = AsyncMock(
        return_value={"released": [], "abandoned": [], "skipped": False}
    )
    worker._sweep_retired_rule_findings = AsyncMock(
        return_value={"resolved": 0, "retired_rules": [], "skipped": False}
    )
    worker._fetch_stale_entries = AsyncMock(
        return_value=[
            {
                "id": 1,
                "entry_type": "claim",
                "subject": "some.subject",
                "worker_uuid": "uuid-1",
                "status": "open",
                "age_seconds": 120,
                "sla_seconds": 60,
            }
        ]
    )
    worker._fetch_existing_findings = AsyncMock(return_value=set())
    worker._count_active_entries = AsyncMock(return_value=1)

    with patch(
        "will.workers.blackboard_shop_manager._CFG",
        MagicMock(reclaim_cap_n=3),
    ):
        import asyncio

        asyncio.run(worker.run())

    worker.post_heartbeat.assert_awaited_once()
    worker.post_finding.assert_awaited_once()
    worker.post_report.assert_awaited_once()
    worker.post_observation.assert_not_awaited()

    finding_kwargs = worker.post_finding.await_args.kwargs
    assert finding_kwargs["subject"] == "blackboard.entry_stale::1"
    assert finding_kwargs["resolution_mechanism"] == "self_resolve"

    report_kwargs = worker.post_report.await_args.kwargs
    assert report_kwargs["subject"] == "blackboard_shop_manager.run.complete"
    assert report_kwargs["payload"]["flagged"] == 1
    assert report_kwargs["payload"]["entries_checked"] == 1
