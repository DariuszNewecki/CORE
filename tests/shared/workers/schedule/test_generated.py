import pytest
from unittest.mock import patch, MagicMock
from typing import Any

from src.shared.workers.schedule import WorkerScheduleState, load_worker_schedule_state


class TestWorkerScheduleState:
    """Tests for the WorkerScheduleState dataclass."""

    def test_schedule_state_creation_with_all_fields(self) -> None:
        """Verify that WorkerScheduleState can be created with all fields."""
        thresholds = {"uuid-1": 120, "uuid-2": 300}
        active_uuids = frozenset({"uuid-1", "uuid-2"})
        fallback_sec = 600

        state = WorkerScheduleState(
            thresholds=thresholds,
            active_uuids=active_uuids,
            fallback_sec=fallback_sec,
        )

        assert state.thresholds == thresholds
        assert state.active_uuids == active_uuids
        assert state.fallback_sec == fallback_sec

    def test_schedule_state_with_empty_thresholds_and_active_uuids(self) -> None:
        """Verify that WorkerScheduleState handles empty collections."""
        state = WorkerScheduleState(
            thresholds={},
            active_uuids=frozenset(),
            fallback_sec=300,
        )

        assert state.thresholds == {}
        assert state.active_uuids == frozenset()
        assert state.fallback_sec == 300

    def test_schedule_state_with_zero_fallback_sec(self) -> None:
        """Verify that fallback_sec can be zero."""
        state = WorkerScheduleState(
            thresholds={},
            active_uuids=frozenset(),
            fallback_sec=0,
        )

        assert state.fallback_sec == 0

    def test_schedule_state_active_uuids_is_immutable(self) -> None:
        """Verify that active_uuids cannot be modified via attribute."""
        state = WorkerScheduleState(
            thresholds={},
            active_uuids=frozenset({"uuid-1"}),
            fallback_sec=100,
        )

        assert state.active_uuids == frozenset({"uuid-1"})
        # Ensure it is a frozenset and remains unchanged
        assert isinstance(state.active_uuids, frozenset)

    def test_schedule_state_thresholds_are_mutable(self) -> None:
        """Verify that thresholds dict can be modified (caller may copy)."""
        thresholds = {"uuid-1": 60}
        state = WorkerScheduleState(
            thresholds=thresholds,
            active_uuids=frozenset(),
            fallback_sec=100,
        )

        # Modifying the original dict does not affect the state (shallow copy at creation)
        thresholds["uuid-1"] = 120
        assert state.thresholds["uuid-1"] == 60

    def test_schedule_state_type_hints(self) -> None:
        """Verify the type hints on the dataclass fields."""
        # Access class-level annotations to verify types
        annotations = WorkerScheduleState.__annotations__
        assert "thresholds" in annotations
        assert annotations["thresholds"] == dict[str, int]
        assert "active_uuids" in annotations
        assert annotations["active_uuids"] == frozenset[str]
        assert "fallback_sec" in annotations
        assert annotations["fallback_sec"] == int


class TestLoadWorkerScheduleState:
    """Tests for the load_worker_schedule_state function."""

    @patch("src.shared.workers.schedule.logger")
    @patch("src.shared.workers.schedule.glob")
    @patch("src.shared.workers.schedule.Path")
    @patch("src.shared.workers.schedule.yaml.safe_load")
    def test_load_returns_empty_state_when_no_workers_dir(
        self,
        mock_safe_load: MagicMock,
        mock_path: MagicMock,
        mock_glob: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Verify that missing .intent/workers/ directory yields empty state."""
        # Simulate that no yaml files are found
        mock_glob.glob.return_value = []
        mock_path.return_value.glob.return_value = []

        result = load_worker_schedule_state()

        assert isinstance(result, WorkerScheduleState)
        assert result.thresholds == {}
        assert result.active_uuids == frozenset()
        assert result.fallback_sec == 300  # Default provided by operational_config
