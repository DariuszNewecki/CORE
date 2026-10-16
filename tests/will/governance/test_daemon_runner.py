# tests/will/governance/test_daemon_runner.py

"""Tests for will.governance.daemon_runner._run_systemctl's timeout handling.

Source: will.governance.daemon_runner

#774 (ADR-040 sweep): _SYSTEMCTL_TIMEOUT_SECONDS existed as a src/ literal
but was never actually applied anywhere -- run_command_async has no native
timeout support, so systemctl calls had no timeout protection at all. This
covers the fix: asyncio.wait_for wrapping sourced from operational_config,
with a real fallback when the config lookup fails.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from shared.utils.subprocess_utils import SubprocessResult
from will.governance.daemon_runner import _run_systemctl, _systemctl_timeout_sec


def test_systemctl_timeout_sec_reads_governed_config() -> None:
    result = _systemctl_timeout_sec()
    assert result == 30.0


def test_systemctl_timeout_sec_falls_back_on_lookup_failure() -> None:
    with patch(
        "will.governance.daemon_runner.load_operational_config",
        side_effect=RuntimeError("config unavailable"),
    ):
        result = _systemctl_timeout_sec()
    assert result == 30.0


async def test_run_systemctl_success_path_unaffected() -> None:
    """The timeout wrapping doesn't change behavior on the success path."""
    completed = SubprocessResult(stdout="ok\n", stderr="", returncode=0)
    with patch(
        "will.governance.daemon_runner.run_command_async",
        new=AsyncMock(return_value=completed),
    ):
        result = await _run_systemctl(("start", "core-daemon"))

    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert result["stdout_tail"] == ["ok"]


async def test_run_systemctl_times_out_returns_error_not_hang() -> None:
    """A hung systemctl call is bounded by asyncio.wait_for -- previously
    the coroutine would have blocked forever (no timeout was ever applied)."""

    async def _never_returns(*args, **kwargs):
        await asyncio.sleep(3600)

    with (
        patch(
            "will.governance.daemon_runner.run_command_async",
            new=_never_returns,
        ),
        patch(
            "will.governance.daemon_runner._systemctl_timeout_sec",
            return_value=0.01,
        ),
    ):
        result = await _run_systemctl(("stop", "core-daemon"))

    assert result["ok"] is False
    assert result["exit_code"] == -1
    assert "timed out" in result["error"]


async def test_run_systemctl_missing_binary_returns_error() -> None:
    with patch(
        "will.governance.daemon_runner.run_command_async",
        new=AsyncMock(side_effect=FileNotFoundError("systemctl")),
    ):
        result = await _run_systemctl(("start", "core-daemon"))

    assert result["ok"] is False
    assert "systemctl not found" in result["error"]


async def test_run_systemctl_generic_exception_returns_error() -> None:
    with patch(
        "will.governance.daemon_runner.run_command_async",
        new=AsyncMock(side_effect=OSError("permission denied")),
    ):
        result = await _run_systemctl(("stop", "core-daemon"))

    assert result["ok"] is False
    assert "permission denied" in result["error"]


# -- get_status: liveness from the registry's real keys (2026-10-15) -----------


async def test_get_status_reads_worker_uuid_and_only_live_workers_are_alive() -> None:
    from datetime import UTC, datetime

    from will.governance.daemon_runner import get_status

    now = datetime(2026, 10, 15, tzinfo=UTC)
    registered = [
        {
            "worker_uuid": "u-live",
            "worker_name": "Live",
            "worker_class": "sensing",
            "phase": "audit",
            "last_heartbeat": now,
            "seconds_silent": 12,
        },
        {
            "worker_uuid": "u-june",
            "worker_name": "June",
            "worker_class": "acting",
            "phase": "execution",
            "last_heartbeat": now,
            "seconds_silent": 9_000_000,
        },
    ]
    alive = [registered[0]]
    service = AsyncMock()
    service.fetch_registered_workers.return_value = registered
    service.fetch_alive_workers.return_value = alive
    from shared.workers.schedule import WorkerScheduleState

    declared = WorkerScheduleState(
        thresholds={"u-live": 132, "u-june": 132},
        active_uuids=frozenset({"u-live", "u-june"}),
        fallback_sec=900,
    )
    with (
        patch(
            "will.governance.daemon_runner.WorkerRegistryService",
            return_value=service,
        ),
        patch(
            "will.governance.daemon_runner.load_worker_schedule_state",
            return_value=declared,
        ),
    ):
        status = await get_status(None)
    by_name = {w["name"]: w for w in status["workers"]}
    assert by_name["Live"]["alive"] is True
    assert by_name["June"]["alive"] is False
    assert by_name["June"]["state"] == "overdue"
    assert by_name["June"]["age_sec"] == 9_000_000
    assert by_name["Live"]["class"] == "sensing"
