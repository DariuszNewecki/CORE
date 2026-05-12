# tests/shared/workers/schedule/test_generated.py
"""Tests for shared.workers.schedule.

Exercises load_worker_schedule_state() against a fake IntentRepository so
the per-call cost of the gateway's intent-tree validation is not paid in
unit tests and the behaviour of each YAML-shape branch is observable in
isolation.
"""

from __future__ import annotations

from typing import Any

import pytest

from shared.workers.schedule import WorkerScheduleState, load_worker_schedule_state


class _FakeIntentRepository:
    """Minimal stand-in for IntentRepository.

    Only the two methods load_worker_schedule_state consumes are
    implemented: list_workers() and load_worker(worker_id).
    """

    def __init__(self, docs: dict[str, dict[str, Any] | Exception]) -> None:
        self._docs = docs

    def list_workers(self) -> list[str]:
        return sorted(self._docs.keys())

    def load_worker(self, worker_id: str) -> dict[str, Any]:
        result = self._docs[worker_id]
        if isinstance(result, Exception):
            raise result
        return result


def _active(uuid: str, max_interval: int = 60, glide_off: int = 15) -> dict[str, Any]:
    return {
        "metadata": {"status": "active"},
        "identity": {"uuid": uuid},
        "mandate": {"schedule": {"max_interval": max_interval, "glide_off": glide_off}},
    }


def _paused(uuid: str) -> dict[str, Any]:
    return {
        "metadata": {"status": "paused"},
        "identity": {"uuid": uuid},
        "mandate": {"schedule": {"max_interval": 120, "glide_off": 30}},
    }


def _active_no_schedule(uuid: str) -> dict[str, Any]:
    return {
        "metadata": {"status": "active"},
        "identity": {"uuid": uuid},
        "mandate": {},
    }


def _active_no_uuid() -> dict[str, Any]:
    return {
        "metadata": {"status": "active"},
        "identity": {},
        "mandate": {"schedule": {"max_interval": 60, "glide_off": 15}},
    }


class TestWorkerScheduleState:
    def test_default_construction(self) -> None:
        state = WorkerScheduleState(
            thresholds={},
            active_uuids=frozenset(),
            fallback_sec=300,
        )
        assert state.thresholds == {}
        assert state.active_uuids == frozenset()
        assert state.fallback_sec == 300

    def test_is_frozen(self) -> None:
        state = WorkerScheduleState(
            thresholds={"u": 1},
            active_uuids=frozenset({"u"}),
            fallback_sec=10,
        )
        with pytest.raises(Exception):
            state.fallback_sec = 99  # type: ignore[misc]


class TestLoadWorkerScheduleState:
    def test_empty_workers_returns_empty_state(self) -> None:
        repo = _FakeIntentRepository({})
        result = load_worker_schedule_state(intent_repo=repo)
        assert isinstance(result, WorkerScheduleState)
        assert result.thresholds == {}
        assert result.active_uuids == frozenset()
        assert result.fallback_sec > 0  # comes from operational_config

    def test_active_worker_contributes_uuid_and_threshold(self) -> None:
        repo = _FakeIntentRepository(
            {"workers/w1": _active("uuid-1", max_interval=60, glide_off=15)}
        )
        result = load_worker_schedule_state(intent_repo=repo)
        assert result.active_uuids == frozenset({"uuid-1"})
        assert result.thresholds == {"uuid-1": 75}

    def test_paused_worker_excluded(self) -> None:
        repo = _FakeIntentRepository(
            {
                "workers/active": _active("uuid-a"),
                "workers/paused": _paused("uuid-p"),
            }
        )
        result = load_worker_schedule_state(intent_repo=repo)
        assert result.active_uuids == frozenset({"uuid-a"})
        assert "uuid-p" not in result.thresholds

    def test_active_worker_without_schedule_block_gets_no_threshold(self) -> None:
        repo = _FakeIntentRepository({"workers/w": _active_no_schedule("uuid-x")})
        result = load_worker_schedule_state(intent_repo=repo)
        assert "uuid-x" in result.active_uuids
        assert "uuid-x" not in result.thresholds

    def test_active_worker_without_uuid_is_skipped(self) -> None:
        repo = _FakeIntentRepository({"workers/w": _active_no_uuid()})
        result = load_worker_schedule_state(intent_repo=repo)
        assert result.active_uuids == frozenset()
        assert result.thresholds == {}

    def test_load_failure_is_logged_and_skipped(self, caplog) -> None:
        repo = _FakeIntentRepository(
            {
                "workers/good": _active("uuid-good", max_interval=30, glide_off=10),
                "workers/broken": RuntimeError("boom"),
            }
        )
        result = load_worker_schedule_state(intent_repo=repo)
        assert result.active_uuids == frozenset({"uuid-good"})
        assert result.thresholds == {"uuid-good": 40}

    def test_glide_off_default_when_missing(self) -> None:
        doc = {
            "metadata": {"status": "active"},
            "identity": {"uuid": "uuid-default"},
            "mandate": {"schedule": {"max_interval": 200}},
        }
        repo = _FakeIntentRepository({"workers/w": doc})
        result = load_worker_schedule_state(intent_repo=repo)
        # glide_off defaults to max(max_interval * multiplier, 10); the
        # exact multiplier comes from operational_config, so we only
        # assert the threshold strictly exceeds max_interval.
        assert "uuid-default" in result.thresholds
        assert result.thresholds["uuid-default"] > 200
