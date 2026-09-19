# tests/shared/workers/test_schedule__launch_on_demand.py
"""#898 — load_worker_schedule_state and ``launch: on_demand``.

``active_uuids`` means "expected to heartbeat". An active worker whose
``implementation.launch`` is ``on_demand`` runs only while a caller invokes
it, so it must contribute neither an active-uuid entry nor a threshold —
otherwise the operational fallback (600s) flags it ``worker.silent`` after
every invocation, which is exactly the live defect the issue records. Its
UUID is reported in ``on_demand_uuids`` for display readers instead.

The IntentRepository gateway is stubbed so the test is hermetic and does
not depend on which workers .intent/ ships today.
"""

from __future__ import annotations

from typing import Any

from shared.workers.schedule import WorkerScheduleState, load_worker_schedule_state


_DAEMON_UUID = "aaaaaaaa-0000-0000-0000-000000000001"
_ON_DEMAND_UUID = "bbbbbbbb-0000-0000-0000-000000000002"
_PAUSED_UUID = "cccccccc-0000-0000-0000-000000000003"


def _decl(
    uuid: str, *, launch: str | None = None, status: str = "active", schedule=None
) -> dict[str, Any]:
    impl: dict[str, Any] = {"module": "will.workers.x", "class": "X"}
    if launch is not None:
        impl["launch"] = launch
    mandate: dict[str, Any] = {"responsibility": "test", "phase": "execution"}
    if schedule is not None:
        mandate["schedule"] = schedule
    return {
        "kind": "worker",
        "metadata": {"id": f"workers.{uuid[:8]}", "status": status},
        "identity": {"uuid": uuid, "class": "acting"},
        "mandate": mandate,
        "implementation": impl,
    }


class _FakeRepo:
    def __init__(self, decls: dict[str, dict[str, Any]]) -> None:
        self._decls = decls

    def list_workers(self) -> list[str]:
        return sorted(self._decls)

    def load_worker(self, worker_id: str) -> dict[str, Any]:
        return self._decls[worker_id]


def _state() -> WorkerScheduleState:
    repo = _FakeRepo(
        {
            "workers/daemon_one": _decl(
                _DAEMON_UUID, schedule={"max_interval": 300, "glide_off": 30}
            ),
            "workers/on_demand_one": _decl(_ON_DEMAND_UUID, launch="on_demand"),
            "workers/paused_one": _decl(_PAUSED_UUID, status="paused"),
        }
    )
    return load_worker_schedule_state(intent_repo=repo)


def test_on_demand_uuid_is_not_in_active_uuids() -> None:
    assert _ON_DEMAND_UUID not in _state().active_uuids


def test_on_demand_uuid_has_no_threshold() -> None:
    assert _ON_DEMAND_UUID not in _state().thresholds


def test_on_demand_uuid_is_reported_in_on_demand_uuids() -> None:
    assert _state().on_demand_uuids == frozenset({_ON_DEMAND_UUID})


def test_daemon_worker_is_unaffected() -> None:
    state = _state()
    assert _DAEMON_UUID in state.active_uuids
    assert state.thresholds[_DAEMON_UUID] == 330
    assert _DAEMON_UUID not in state.on_demand_uuids


def test_paused_worker_is_in_neither_set() -> None:
    state = _state()
    assert _PAUSED_UUID not in state.active_uuids
    assert _PAUSED_UUID not in state.on_demand_uuids
    assert _PAUSED_UUID not in state.thresholds


def test_absent_launch_key_means_daemon() -> None:
    """Backward compatibility: every pre-#898 declaration (no launch key)
    keeps being supervised exactly as before."""
    repo = _FakeRepo({"workers/legacy": _decl(_DAEMON_UUID)})
    state = load_worker_schedule_state(intent_repo=repo)
    assert state.active_uuids == frozenset({_DAEMON_UUID})
    assert state.on_demand_uuids == frozenset()


def test_dataclass_default_keeps_direct_constructors_working() -> None:
    """worker_shop_manager.py and existing tests construct the dataclass
    without on_demand_uuids; the field must default."""
    s = WorkerScheduleState(thresholds={}, active_uuids=frozenset(), fallback_sec=60)
    assert s.on_demand_uuids == frozenset()
