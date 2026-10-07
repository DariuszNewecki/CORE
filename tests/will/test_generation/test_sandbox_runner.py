# tests/will/test_generation/test_sandbox_runner.py
"""PytestSandboxRunner routes pytest through shared.utils.subprocess_utils."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.utils.subprocess_utils import SubprocessResult
from will.test_generation import sandbox
from will.test_generation.sandbox import PytestSandboxRunner


def _runner(repo_root: Path) -> PytestSandboxRunner:
    (repo_root / "var" / "tmp").mkdir(parents=True)
    return PytestSandboxRunner(file_handler=MagicMock(), repo_root=str(repo_root))


@pytest.mark.asyncio
async def test_run_routes_pytest_with_env_and_cwd(monkeypatch, tmp_path):
    fake = AsyncMock(
        return_value=SubprocessResult("t.py::test_a PASSED\nt.py::test_b PASSED", "", 0)
    )
    monkeypatch.setattr(sandbox, "run_command_async", fake)

    result = await _runner(tmp_path).run("def test_a(): pass", "sym")

    assert result.passed is True
    assert result.error == ""
    assert result.passed_tests == ["test_a", "test_b"]
    assert result.total_tests == 2

    args = fake.await_args.args[0]
    kwargs = fake.await_args.kwargs
    assert args[0] == "pytest"
    assert args[-1].endswith("test_sym_sandbox.py")
    sandbox_root = Path(kwargs["cwd"])
    assert sandbox_root.parent == tmp_path / "var" / "tmp"
    assert kwargs["env"]["PYTHONPATH"].startswith(f"{sandbox_root}:{tmp_path}/src:")


@pytest.mark.asyncio
async def test_run_failure_joins_stdout_and_stderr_on_newline(monkeypatch, tmp_path):
    fake = AsyncMock(
        return_value=SubprocessResult("t.py::test_a FAILED", "ImportError: x", 1)
    )
    monkeypatch.setattr(sandbox, "run_command_async", fake)

    result = await _runner(tmp_path).run("code", "sym")

    assert result.passed is False
    assert result.error == "t.py::test_a FAILED\nImportError: x"
    assert result.failed_tests == ["test_a"]


@pytest.mark.asyncio
async def test_run_timeout_returns_sandbox_result(monkeypatch, tmp_path):
    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(sandbox, "run_command_async", _hang)

    result = await _runner(tmp_path).run("code", "sym", timeout_seconds=0.05)

    assert result.passed is False
    assert result.error == "Execution timeout (0.05s)."
    assert result.total_tests == 0


@pytest.mark.asyncio
async def test_run_missing_pytest_is_reported_not_raised(monkeypatch, tmp_path):
    fake = AsyncMock(side_effect=FileNotFoundError("pytest"))
    monkeypatch.setattr(sandbox, "run_command_async", fake)

    result = await _runner(tmp_path).run("code", "sym")

    assert result.passed is False
    assert "pytest" in result.error
