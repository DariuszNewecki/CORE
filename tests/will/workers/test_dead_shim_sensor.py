# tests/will/workers/test_dead_shim_sensor.py

"""
ADR-151 sensor tests — the D2 __all__ grace, finding lifecycle, and the
day-one live catch shape (sync_manifest).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.dead_shim_sensor import _SUBJECT_PREFIX, DeadShimSensor


_SYNC_MANIFEST_ROW = {
    "symbol_path": "src/cli/logic/sync_manifest.py::sync_manifest",
    "module": "cli.logic.sync_manifest",
    "qualname": "sync_manifest",
    "kind": "function",
}

_GRACED_ROW = {
    # ActionResult is in shared.__all__ — the published extension contract.
    "symbol_path": "src/shared/action_types.py::ActionResult",
    "module": "shared.action_types",
    "qualname": "ActionResult",
    "kind": "class",
}


def _make_sensor() -> DeadShimSensor:
    w = object.__new__(DeadShimSensor)
    w._declaration = {}
    w._max_interval = 600
    w._core_context = None
    w.post_heartbeat = AsyncMock()  # type: ignore[method-assign]
    w.post_finding = AsyncMock()  # type: ignore[method-assign]
    w.post_report = AsyncMock()  # type: ignore[method-assign]
    return w


def _make_registry(candidates, existing):
    symbol_svc = MagicMock()
    symbol_svc.fetch_dead_shim_candidates = AsyncMock(return_value=candidates)
    blackboard_svc = MagicMock()
    blackboard_svc.fetch_open_findings = AsyncMock(return_value=existing)
    blackboard_svc.resolve_entries = AsyncMock()
    registry = MagicMock()
    registry.get_symbol_service = AsyncMock(return_value=symbol_svc)
    registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)
    return registry, blackboard_svc


async def _run(sensor, registry) -> None:
    with patch("body.services.service_registry.service_registry", registry):
        await sensor.run()


async def test_day_one_live_catch_posts_finding():
    sensor = _make_sensor()
    registry, _ = _make_registry([_SYNC_MANIFEST_ROW], existing=[])

    await _run(sensor, registry)

    call = sensor.post_finding.await_args
    assert call.kwargs["subject"] == f"{_SUBJECT_PREFIX}::{_SYNC_MANIFEST_ROW['symbol_path']}"
    assert call.kwargs["payload"]["rule"] == "modernization.dead_shim"
    assert "verify-then-delete" in call.kwargs["payload"]["remediation_contract"]
    assert call.kwargs["resolution_mechanism"] == "self_resolve"


async def test_published_contract_symbol_is_graced():
    """ActionResult sits in shared.__all__ — D2 grace, no finding."""
    sensor = _make_sensor()
    registry, _ = _make_registry([_GRACED_ROW], existing=[])

    await _run(sensor, registry)

    sensor.post_finding.assert_not_awaited()
    report = sensor.post_report.await_args.kwargs["payload"]
    assert report["graced_published_contract"] == 1
    assert report["flagged"] == 0


async def test_programmatic_cli_command_is_path_graced():
    """The measured gap: register_drift_commands wires deprecated Typer
    commands with no decorator — the dispatch grace must hold by path."""
    sensor = _make_sensor()
    row = {
        "symbol_path": "src/cli/commands/inspect/drift.py::symbol_drift_cmd",
        "module": "cli.commands.inspect.drift",
        "qualname": "symbol_drift_cmd",
        "kind": "function",
    }
    registry, _ = _make_registry([row], existing=[])

    await _run(sensor, registry)

    sensor.post_finding.assert_not_awaited()
    report = sensor.post_report.await_args.kwargs["payload"]
    assert report["graced_dispatch_surface"] == 1


async def test_open_finding_not_reposted():
    sensor = _make_sensor()
    subject = f"{_SUBJECT_PREFIX}::{_SYNC_MANIFEST_ROW['symbol_path']}"
    registry, _ = _make_registry(
        [_SYNC_MANIFEST_ROW], existing=[{"subject": subject, "id": "eid-1"}]
    )

    await _run(sensor, registry)

    sensor.post_finding.assert_not_awaited()


async def test_cleared_condition_self_resolves():
    """Symbol left the candidate set (deleted / gained a caller) → resolve."""
    sensor = _make_sensor()
    subject = f"{_SUBJECT_PREFIX}::src/gone.py::gone_symbol"
    registry, blackboard_svc = _make_registry(
        candidates=[], existing=[{"subject": subject, "id": "eid-2"}]
    )

    await _run(sensor, registry)

    blackboard_svc.resolve_entries.assert_awaited_once_with(["eid-2"])
    report = sensor.post_report.await_args.kwargs["payload"]
    assert report["resolved"] == 1
