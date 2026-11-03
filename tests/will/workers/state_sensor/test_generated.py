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


from will.workers.state_sensor import law_drift_subjects


# ID: efd78e64-30ce-4e6a-a401-7ab9c14ff110
def test_law_drift_subjects():
    law = MagicMock()
    law.relationship = "DRIFT"
    law.drift_paths = ["src/a.py", "src/b.py"]

    result = law_drift_subjects(law)

    assert result == {
        "governance::law_drift::src/a.py": "src/a.py",
        "governance::law_drift::src/b.py": "src/b.py",
    }


from types import SimpleNamespace


# ID: a56a3c95-0292-416f-8539-066377ba0973
async def test_StateSensor():
    worker = StateSensor()
    worker.post_heartbeat = AsyncMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()

    worker._core_context = SimpleNamespace(
        git_service=SimpleNamespace(repo_path="/tmp/repo")
    )

    law = SimpleNamespace(
        relationship="MATCH",
        head_sha="deadbeefcafe",
        record_digest="rec",
        evaluated_digest="eval",
        reason=None,
    )
    observation = SimpleNamespace(
        head_sha="deadbeefcafe",
        dirty_paths=[],
        law_state=law,
    )

    mock_ledger = MagicMock()
    # record_if_changed returns [] on first run -> changes is not None -> True
    mock_ledger.record_if_changed = AsyncMock(return_value=[])

    mock_blackboard = MagicMock()
    mock_blackboard.fetch_open_findings = AsyncMock(return_value=[])
    mock_blackboard.resolve_entries = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_blackboard)

    worker._sync_law_drift = AsyncMock(return_value=(0, 0, 0))
    worker._sync_stale_daemon = AsyncMock(return_value={"code_state": "CLEAN"})
    worker._sync_law_venv = AsyncMock(return_value={"law_venv": "n/a"})
    worker._sync_access = AsyncMock(return_value={})
    worker._sync_ledger_signatures = AsyncMock(return_value={})
    worker._post_unattributed = AsyncMock(return_value=0)

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "body.services.state_ledger_service.StateLedgerService",
            return_value=mock_ledger,
        ),
        patch(
            "body.services.state_ledger_service.observe_state",
            return_value=observation,
        ),
        patch(
            "shared.path_resolver.PathResolver",
        ) as mock_path_resolver,
        patch(
            "will.workers.state_sensor.loaded_code_identity",
            return_value="identity-abc",
        ),
    ):
        mock_path_resolver.return_value.intent_root = "/tmp/repo/intent"

        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    mock_ledger.record_if_changed.assert_awaited_once_with(observation)
    worker.post_report.assert_awaited_once()

    _, kwargs = worker.post_report.call_args
    assert kwargs["subject"] == "state_sensor.run.complete"
    assert kwargs["payload"]["head_sha"] == "deadbeefcafe"
    assert kwargs["payload"]["law_relationship"] == "MATCH"
    # changes is [] (not None) -> ledger_row_appended is True
    assert kwargs["payload"]["ledger_row_appended"] is True
    assert kwargs["payload"]["changes_attributed"] == 0


from datetime import UTC, datetime, timedelta

from will.workers.state_sensor import escalation_due


# ID: 29f8e7dc-f617-479c-aaf0-7b9b4fa5ecd0
def test_escalation_due():
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    window_minutes = 30

    # Observed exactly at the window boundary -> due (>= comparison).
    at_boundary = (now - timedelta(minutes=window_minutes)).isoformat()
    assert escalation_due(at_boundary, window_minutes, now) is True

    # Observed well past the window -> due.
    long_ago = (now - timedelta(minutes=window_minutes + 10)).isoformat()
    assert escalation_due(long_ago, window_minutes, now) is True

    # Observed recently, inside the window -> not due.
    recent = (now - timedelta(minutes=5)).isoformat()
    assert escalation_due(recent, window_minutes, now) is False

    # Naive timestamp is treated as UTC.
    naive_recent = (now - timedelta(minutes=1)).replace(tzinfo=None).isoformat()
    assert escalation_due(naive_recent, window_minutes, now) is False

    # Missing timestamp -> treated as due (fail-open).
    assert escalation_due(None, window_minutes, now) is True
    assert escalation_due("", window_minutes, now) is True

    # Unparseable timestamp -> treated as due (fail-open).
    assert escalation_due("not-a-date", window_minutes, now) is True




# ID: c7581065-3e22-4521-a674-66ba781f1cc6
def test_unattributed_law_changes():
    from will.workers.state_sensor import (
        UNREADABLE_RANGE_PATH,
        unattributed_law_changes,
    )

    # ID: 7bee007e-239e-4679-9e50-b4c49949db59
    def make_change(path, persistence="committed", producer_provenance="unknown"):
        change = MagicMock()
        change.path = path
        change.persistence = persistence
        change.producer_provenance = producer_provenance
        return change

    attributed = make_change(".intent/law.py", producer_provenance="known")
    uncommitted = make_change(".intent/law.py", persistence="uncommitted")
    src_change = make_change("src/foo.py")
    matched = make_change(".intent/other.py")
    unreadable = make_change(UNREADABLE_RANGE_PATH)

    changes = [attributed, uncommitted, src_change, matched, unreadable]

    result = unattributed_law_changes(changes)

    assert result == [matched, unreadable]
