from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.workers.state_sensor import StateSensor


@pytest.mark.asyncio
# ID: c3339306-b596-46eb-b4d2-479a2df2b4d5
async def test_StateSensor_run():
    sensor = StateSensor(core_context=MagicMock())

    # core context / git service paths
    repo_root = "/tmp/repo"
    sensor._core_context.git_service.repo_path = repo_root

    observation = MagicMock()
    observation.head_sha = "abc123"
    observation.dirty_paths = ["a", "b"]
    observation.law_state = MagicMock()
    observation.law_state.relationship = "compliant"

    changes = [MagicMock(), MagicMock()]

    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = AsyncMock()
    sensor._sync_law_drift = AsyncMock(return_value=(1, 2, 3))
    sensor._sync_stale_daemon = AsyncMock(return_value={"stale_daemon": "x"})
    sensor._sync_law_venv = AsyncMock(return_value={"law_venv": "y"})
    sensor._sync_access = AsyncMock(return_value={"access": "z"})
    sensor._sync_ledger_signatures = AsyncMock(return_value={"signatures": "s"})
    sensor._post_unattributed = AsyncMock(return_value=7)

    mock_ledger = MagicMock()
    mock_ledger.record_if_changed = AsyncMock(return_value=changes)

    mock_blackboard = MagicMock()
    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_blackboard)

    with (
        patch(
            "body.services.service_registry.service_registry",
            mock_registry,
        ),
        patch(
            "body.services.state_ledger_service.observe_state",
            return_value=observation,
        ),
        patch(
            "body.services.state_ledger_service.StateLedgerService",
            return_value=mock_ledger,
        ),
        patch(
            "shared.path_resolver.PathResolver",
        ) as mock_path_resolver,
        patch(
            "will.workers.state_sensor.loaded_code_identity",
            return_value="identity-sha",
        ),
    ):
        mock_path_resolver.return_value.intent_root = "/tmp/repo/intent"
        await sensor.run()

    sensor.post_heartbeat.assert_awaited_once()
    sensor.post_report.assert_awaited_once()
    sensor._sync_law_drift.assert_awaited_once_with(
        mock_blackboard, observation.law_state
    )
    sensor._sync_stale_daemon.assert_awaited_once_with(mock_blackboard)
    sensor._sync_law_venv.assert_awaited_once_with(mock_blackboard)
    sensor._sync_access.assert_awaited_once_with(mock_blackboard, repo_root)
    sensor._sync_ledger_signatures.assert_awaited_once_with(mock_blackboard, repo_root)
    sensor._post_unattributed.assert_awaited_once_with(changes)

    call_kwargs = sensor.post_report.call_args.kwargs
    assert call_kwargs["subject"] == "state_sensor.run.complete"
    payload = call_kwargs["payload"]
    assert payload["head_sha"] == "abc123"
    assert payload["dirty_paths"] == 2
    assert payload["law_relationship"] == "compliant"
    assert payload["law_drift_open"] == 1
    assert payload["law_drift_posted"] == 2
    assert payload["law_drift_resolved"] == 3
    assert payload["ledger_row_appended"] is True
    assert payload["changes_attributed"] == 2
    assert payload["unattributed_posted"] == 7
    assert payload["stale_daemon"] == "x"
    assert payload["law_venv"] == "y"
    assert payload["access"] == "z"
    assert payload["signatures"] == "s"
