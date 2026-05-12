import pytest
from shared.workers.schedule import WorkerScheduleState, load_worker_schedule_state
from unittest.mock import patch, MagicMock, mock_open
import dataclasses
import pathlib
import yaml


class TestWorkerScheduleState:
    """Test suite for the WorkerScheduleState dataclass."""

    def test_default_construction(self):
        """Verify default construction yields expected empty state."""
        state = WorkerScheduleState(
            thresholds={},
            active_uuids=frozenset(),
            fallback_sec=300,
        )
        assert state.thresholds == {}
        assert state.active_uuids == frozenset()
        assert state.fallback_sec == 300

    def test_typed_fields_present(self):
        """Ensure all expected fields exist with correct types."""
        thresholds = {"uuid-1": 120, "uuid-2": 180}
        active_uuids = frozenset({"uuid-1", "uuid-3"})
        state = WorkerScheduleState(
            thresholds=thresholds,
            active_uuids=active_uuids,
            fallback_sec=60,
        )
        assert isinstance(state.thresholds, dict)
        assert isinstance(state.active_uuids, frozenset)
        assert isinstance(state.fallback_sec, int)
        assert state.thresholds == thresholds
        assert state.active_uuids == active_uuids
        assert state.fallback_sec == 60

    def test_thresholds_empty_active_uuids_non_empty(self):
        """Edge case: thresholds empty but active_uuids has entries."""
        state = WorkerScheduleState(
            thresholds={},
            active_uuids=frozenset({"worker-a"}),
            fallback_sec=120,
        )
        assert state.thresholds == {}
        assert "worker-a" in state.active_uuids


class TestLoadWorkerScheduleState:
    """Test suite for load_worker_schedule_state function."""

    def test_returns_worker_schedule_state_instance(self):
        """Verify function always returns a WorkerScheduleState."""
        with patch("shared.workers.schedule._load_from_disk") as mock_load:
            mock_load.return_value = WorkerScheduleState(
                thresholds={},
                active_uuids=frozenset(),
                fallback_sec=300,
            )
            result = load_worker_schedule_state()
            assert isinstance(result, WorkerScheduleState)

    def test_missing_directory_returns_empty_state(self):
        """Simulate missing .intent/workers/ directory."""
        with patch(
            "shared.workers.schedule._load_from_disk",
            side_effect=FileNotFoundError,
        ):
            with patch("shared.workers.schedule.logger") as mock_logger:
                result = load_worker_schedule_state()
                assert isinstance(result, WorkerScheduleState)
                assert result.thresholds == {}
                assert result.active_uuids == frozenset()
                mock_logger.warning.assert_called_once()

    def test_parses_single_active_yaml_correctly(self):
        """YAML with status: active yields threshold and uuid entry."""
        yaml_content = """
uuid: worker-1
status: active
mandate:
  schedule:
    max_interval: 60
    glide_off: 15
"""
        mock_path = MagicMock(spec=pathlib.Path)
        mock_path.name = "worker-1.yaml"
        mock_path.open.return_value.__enter__.return_value = yaml_content

        with patch("shared.workers.schedule._discover_yamls") as mock_discover:
            mock_discover.return_value = [mock_path]
            with patch("shared.workers.schedule._compute_threshold") as mock_thresh:
                mock_thresh.return_value = 75
                result = load_worker_schedule_state()
                assert "worker-1" in result.active_uuids
                assert result.thresholds.get("worker-1") == 75

    def test_paused_yaml_produces_no_entries(self):
        """Worker with status: paused should be excluded."""
        yaml_content = """
uuid: worker-paused
status: paused
mandate:
  schedule:
    max_interval: 120
"""
        mock_path = MagicMock(spec=pathlib.Path)
        mock_path.name = "paused.yaml"
        mock_path.open.return_value
