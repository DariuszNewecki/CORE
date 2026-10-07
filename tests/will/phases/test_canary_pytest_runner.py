# tests/will/phases/test_canary_pytest_runner.py
"""Canary PytestRunner routes pytest through shared.utils.subprocess_utils."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.utils.subprocess_utils import SubprocessResult
from will.phases.canary import pytest_runner
from will.phases.canary.pytest_runner import PytestRunner


def _runner(**kwargs) -> PytestRunner:
    paths = SimpleNamespace(repo_root=Path("/repo"))
    return PytestRunner(path_resolver=paths, **kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_run_tests_collects_then_executes(monkeypatch):
    fake = AsyncMock(
        side_effect=[
            SubprocessResult("collected 2 items", "", 0),
            SubprocessResult("t::a PASSED\nt::b FAILED", "warn", 1),
        ]
    )
    monkeypatch.setattr(pytest_runner, "run_command_async", fake)

    result = await _runner().run_tests(["tests/t.py"])

    assert result == {
        "passed": 1,
        "failed": 1,
        "exit_code": 1,
        "output": "t::a PASSED\nt::b FAILED\nwarn",
    }
    collect_call, exec_call = fake.await_args_list
    assert "--co" in collect_call.args[0]
    assert "-x" in exec_call.args[0]
    assert collect_call.kwargs["cwd"] == Path("/repo")
    assert exec_call.args[0][-1] == "tests/t.py"


@pytest.mark.asyncio
async def test_run_tests_no_tests_collected(monkeypatch):
    fake = AsyncMock(return_value=SubprocessResult("no tests ran in 0.01s", "", 5))
    monkeypatch.setattr(pytest_runner, "run_command_async", fake)

    result = await _runner().run_tests(["tests/t.py"])

    assert result == {
        "passed": 0,
        "failed": 0,
        "exit_code": 0,
        "output": "No tests collected",
    }
    fake.assert_awaited_once()


@pytest.mark.asyncio
async def test_collection_timeout_returns_false(monkeypatch):
    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(pytest_runner, "run_command_async", _hang)

    runner = _runner(collection_timeout=0.05)
    assert await runner._verify_collection(["tests/t.py"]) is False


@pytest.mark.asyncio
async def test_execution_timeout_returns_124(monkeypatch):
    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(pytest_runner, "run_command_async", _hang)

    result = await _runner(execution_timeout=0.05)._execute_tests(["tests/t.py"])

    assert result["exit_code"] == 124
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_execution_error_returns_exit_1(monkeypatch):
    fake = AsyncMock(side_effect=FileNotFoundError("pytest"))
    monkeypatch.setattr(pytest_runner, "run_command_async", fake)

    result = await _runner()._execute_tests(["tests/t.py"])

    assert result["exit_code"] == 1
    assert "pytest" in result["output"]
