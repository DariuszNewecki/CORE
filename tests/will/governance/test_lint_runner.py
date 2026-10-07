# tests/will/governance/test_lint_runner.py
"""lint_runner routes its tool runs through shared.utils.subprocess_utils."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from shared.utils.subprocess_utils import SubprocessResult
from will.governance import lint_runner


@pytest.mark.asyncio
async def test_run_tool_routes_through_run_command_async(monkeypatch):
    fake = AsyncMock(return_value=SubprocessResult("out", "err", 1))
    monkeypatch.setattr(lint_runner, "run_command_async", fake)

    result = await lint_runner._run_tool(Path("/venv/bin/ruff"), ["check", "src"])

    fake.assert_awaited_once_with(["/venv/bin/ruff", "check", "src"])
    assert result == {"returncode": 1, "stdout": "out", "stderr": "err"}


@pytest.mark.asyncio
async def test_run_tool_real_process_nonzero_exit_is_returned():
    result = await lint_runner._run_tool(
        Path(sys.executable),
        ["-c", "import sys; print('hi'); sys.stderr.write('bad'); sys.exit(3)"],
    )
    assert result == {"returncode": 3, "stdout": "hi", "stderr": "bad"}


@pytest.mark.asyncio
async def test_run_lint_aggregates_both_tools(monkeypatch, tmp_path):
    (tmp_path / "black").touch()
    (tmp_path / "ruff").touch()
    monkeypatch.setattr(lint_runner, "_VENV_BIN", tmp_path)
    fake = AsyncMock(
        side_effect=[SubprocessResult("", "", 0), SubprocessResult("E1", "", 1)]
    )
    monkeypatch.setattr(lint_runner, "run_command_async", fake)

    result = await lint_runner.run_lint()

    assert result["ok"] is False
    assert result["error"] is None
    assert result["tools"]["black"]["returncode"] == 0
    assert result["tools"]["ruff"] == {"returncode": 1, "stdout": "E1", "stderr": ""}
    assert fake.await_args_list[0].args[0] == [
        str(tmp_path / "black"),
        "--check",
        "src",
        "tests",
    ]


@pytest.mark.asyncio
async def test_run_lint_reports_missing_binaries(monkeypatch, tmp_path):
    monkeypatch.setattr(lint_runner, "_VENV_BIN", tmp_path)
    fake = AsyncMock()
    monkeypatch.setattr(lint_runner, "run_command_async", fake)

    result = await lint_runner.run_lint()

    assert result["ok"] is False
    assert result["tools"] == {}
    assert "black" in result["error"] and "ruff" in result["error"]
    fake.assert_not_awaited()
