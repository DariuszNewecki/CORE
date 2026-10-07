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
