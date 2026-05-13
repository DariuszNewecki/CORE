from typing import Any, Dict, Set
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch, mock_open, PropertyMock
from src.shared.workers.schedule import WorkerScheduleState, load_worker_schedule_state


class TestWorkerScheduleState:
    """Test suite for the WorkerScheduleState dataclass."""

    def test_init_with_defaults(self):
        """Verify default values are set correctly when creating an empty state."""
        state = WorkerScheduleState(thresholds={}, active_uuids=frozenset(), fallback_sec=300)
        assert state.thresholds == {}
        assert state.active_uuids == frozenset()
        assert state.fallback_sec == 300

    def test_init_with_values(self):
        """Verify custom values are stored correctly when provided."""
        thresholds = {"uuid-1": 120, "uuid-2": 60}
        active_uuids = frozenset({"uuid-1"})
        state = WorkerScheduleState(thresholds=thresholds, active_uuids=active_uuids, fallback_sec=180)
        assert state.thresholds == thresholds
        assert state.active_uuids == active_uuids
        assert state.fallback_sec == 180

    def test_thresholds_type_enforcement(self):
        """Ensure the thresholds attribute accepts a dictionary with string keys and int values."""
        test_thresholds: Dict[str, int] = {"abc": 30, "def": 90}
        state = WorkerScheduleState(thresholds=test_thresholds, active_uuids=frozenset(), fallback_sec=0)
        assert isinstance(state.thresholds, dict)
        for key, value in state.thresholds.items():
            assert isinstance(key, str)
            assert isinstance(value, int)

    def test_active_uuids_is_frozenset(self):
        """Verify active_uuids is stored as an immutable frozenset."""
        state = WorkerScheduleState(thresholds={}, active_uuids=frozenset(), fallback_sec=0)
        assert isinstance(state.active_uuids, frozenset)

    def test_fallback_sec_is_integer(self):
        """Ensure fallback_sec attribute is stored as an integer."""
        state = WorkerScheduleState(thresholds={}, active_uuids=frozenset(), fallback_sec=300)
        assert isinstance(state.fallback_sec, int)

    def test_equality_based_on_all_fields(self):
        """Verify two identical instances compare equal, differing ones are not equal."""
        state1 = WorkerScheduleState(thresholds={"x": 10}, active_uuids=frozenset({"x"}), fallback_sec=60)
        state2 = WorkerScheduleState(thresholds={"x": 10}, active_uuids=frozenset({"x"}), fallback_sec=60)
        state3 = WorkerScheduleState(thresholds={"y": 20}, active_uuids=frozenset({"x"}), fallback_sec=60)
        assert state1 == state2
        assert state1 != state3

    def test_repr_contains_all_fields(self):
        """Confirm the repr output includes the class name and all attribute values."""
        state = WorkerScheduleState(thresholds={"z": 40}, active_uuids=frozenset({"z"}), fallback_sec=120)
        repr_output = repr(state)
        assert "WorkerScheduleState" in repr_output
        assert "thresholds" in repr_output
        assert "active_uuids" in repr_output
        assert "fallback_sec" in repr_output


class TestLoadWorkerScheduleState:
    """Test suite for the load_worker_schedule_state function."""

    @patch("src.shared.workers.schedule.os.path.isdir")
    @patch("src.shared.workers.schedule.os.listdir")
    @patch("src.shared.workers.schedule.open", new_callable=mock_open, read_data='uuid: "uuid-1"\nstatus: active\nmandate:\n  schedule:\n    max_interval: 60\n    glide_off: 10\n')
    @patch("src.shared.workers.schedule.Path")
    def test_returns_worker_schedule_state_instance(self, MockPath, mock_file, mock_listdir, mock_isdir):
        """Verify the function returns a WorkerScheduleState instance, not None or another type."""
        mock_isdir.return_value = True
        mock_listdir.return_value = ["worker1.yaml"]
        mock_path_instance = MagicMock(spec=Path)
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = False
        MockPath.return_value = mock_path_instance
        result
