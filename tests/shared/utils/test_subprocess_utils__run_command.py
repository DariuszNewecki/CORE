"""Tests for ``run_command`` / ``run_command_async`` -- the general-purpose
sanctioned subprocess entry points.

These exist so callers stop shortcutting around ``shared.utils.subprocess_utils``
(the ``governance.dangerous_execution_primitives`` excludes list, 2026-10-06).
The properties callers needed and hand-rolled: an explicit child environment,
a timeout that kills the child (``asyncio.wait_for`` around the old async
helper cancelled the wait and orphaned the process), and a quiet synchronous
runner.

Real child processes (``sys.executable -c``), not mocks: the kill-and-reap
property is only meaningful against a real process.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

from shared.utils.subprocess_utils import (
    SubprocessCommandError,
    SubprocessTimeoutError,
    run_command,
    run_command_async,
)


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


# --- run_command_async -------------------------------------------------------


async def test_async_captures_streams_and_returns_nonzero_exit() -> None:
    result = await run_command_async(
        _py("import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)")
    )
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.returncode == 3


async def test_async_runs_in_cwd(tmp_path: Path) -> None:
    result = await run_command_async(_py("import os; print(os.getcwd())"), cwd=tmp_path)
    assert Path(result.stdout).resolve() == tmp_path.resolve()


async def test_async_env_is_the_complete_child_environment() -> None:
    os.environ["CORE_TEST_PARENT_ONLY"] = "leak"
    try:
        result = await run_command_async(
            _py(
                "import os; print(os.environ.get('CORE_TEST_CHILD', '-'),"
                " os.environ.get('CORE_TEST_PARENT_ONLY', '-'))"
            ),
            env={"CORE_TEST_CHILD": "set"},
        )
    finally:
        del os.environ["CORE_TEST_PARENT_ONLY"]
    assert result.stdout == "set -"


async def test_async_caller_timeout_kills_child_without_waiting_it_out() -> None:
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            run_command_async(_py("import time; time.sleep(30)")), timeout=0.5
        )
    assert time.monotonic() - started < 10


async def test_async_caller_timeout_leaves_no_orphan(tmp_path: Path) -> None:
    """The bug this closes: wait_for around the old helper cancelled the wait
    and left the child running."""
    pid_file = tmp_path / "pid"
    code = (
        "import os, pathlib, time;"
        f" pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()));"
        " time.sleep(30)"
    )
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(run_command_async(_py(code)), timeout=1.0)
    assert not _pid_alive(int(pid_file.read_text()))


async def test_async_asyncio_timeout_context_also_reaps(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"
    code = (
        "import os, pathlib, time;"
        f" pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()));"
        " time.sleep(30)"
    )
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(1.0):
            await run_command_async(_py(code))
    assert not _pid_alive(int(pid_file.read_text()))


async def test_async_undecodable_output_is_replaced_not_raised() -> None:
    result = await run_command_async(
        _py("import sys; sys.stdout.buffer.write(b'ok \\xff')")
    )
    assert result.stdout == "ok �"


# --- run_command (sync) ------------------------------------------------------


def test_sync_captures_streams_and_returns_nonzero_exit() -> None:
    result = run_command(
        _py("import sys; print(' out '); print('err', file=sys.stderr); sys.exit(2)")
    )
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.returncode == 2


def test_sync_runs_in_cwd_with_env(tmp_path: Path) -> None:
    result = run_command(
        _py("import os; print(os.getcwd()); print(os.environ.get('CORE_TEST_CHILD'))"),
        cwd=tmp_path,
        env={"CORE_TEST_CHILD": "set"},
    )
    cwd_line, env_line = result.stdout.splitlines()
    assert Path(cwd_line).resolve() == tmp_path.resolve()
    assert env_line == "set"


def test_sync_timeout_raises_typed_error() -> None:
    with pytest.raises(SubprocessTimeoutError) as excinfo:
        run_command(_py("import time; time.sleep(30)"), timeout=0.5)
    assert isinstance(excinfo.value, TimeoutError)
    assert isinstance(excinfo.value, SubprocessCommandError)
    assert excinfo.value.exit_code == 124


def test_sync_missing_executable_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        run_command(["core-definitely-not-an-executable"])


def test_sync_does_not_log_output_at_info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="shared.utils.subprocess_utils")
    run_command(_py('print(\'{"json": "payload"}\')'))
    assert "payload" not in caplog.text


# --- workers that inherit the pipe (CI hang, run 37670816047) ----------------
#
# black / pytest-xdist start workers that inherit the output pipe. Killing only
# the command left the workers holding the pipe, and waiting for the pipe never
# returned: the hermetic CI job hung until its 15-minute limit.


def _spawn_worker_and_sleep(pid_file: Path) -> list[str]:
    return _py(
        "import pathlib, subprocess, sys, time;"
        " w = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
        f" pathlib.Path({str(pid_file)!r}).write_text(str(w.pid));"
        " time.sleep(60)"
    )


async def test_async_timeout_kills_workers_holding_the_pipe(tmp_path: Path) -> None:
    pid_file = tmp_path / "worker_pid"
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        # Outer bound: without the fix the inner cancellation never completes.
        await asyncio.wait_for(
            _inner_timeout(run_command_async(_spawn_worker_and_sleep(pid_file))),
            timeout=15,
        )
    assert time.monotonic() - started < 10
    assert not _pid_alive(int(pid_file.read_text()))


async def _inner_timeout(coro) -> None:
    await asyncio.wait_for(coro, timeout=1.0)


def test_sync_timeout_kills_workers_holding_the_pipe(tmp_path: Path) -> None:
    import threading

    pid_file = tmp_path / "worker_pid"
    outcome: list[BaseException] = []

    def _run() -> None:
        try:
            run_command(_spawn_worker_and_sleep(pid_file), timeout=1.0)
        except BaseException as exc:
            outcome.append(exc)

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(timeout=15)
    assert not worker.is_alive(), "run_command hung on a worker holding the pipe"
    assert isinstance(outcome[0], SubprocessTimeoutError)
    assert not _pid_alive(int(pid_file.read_text()))


# --- the group kill must never reach the caller's own group -------------------
#
# killpg(0) signals the caller's own process group, and a MagicMock process's
# pid coerces to 1. Either would take down the test runner, the daemon, or the
# terminal session. os.killpg is replaced by a recorder, so a regression here
# fails the assertion instead of sending a signal.


@pytest.mark.parametrize("pid_factory", ["zero", "one", "own_group", "mock"])
def test_kill_group_refuses_pids_that_are_not_a_child_group(
    monkeypatch: pytest.MonkeyPatch, pid_factory: str
) -> None:
    from unittest.mock import MagicMock

    from shared.utils import subprocess_utils

    pid = {
        "zero": lambda: 0,
        "one": lambda: 1,
        "own_group": os.getpgrp,
        "mock": lambda: MagicMock().pid,
    }[pid_factory]()
    signalled: list[object] = []
    monkeypatch.setattr(subprocess_utils.os, "killpg", lambda *a: signalled.append(a))

    subprocess_utils._kill_group(pid)

    assert signalled == []
