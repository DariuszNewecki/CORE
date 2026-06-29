# tests/body/atomic/test_tool_runner.py

"""Unit tests for ToolRunner — the validated-diff subprocess sanctuary (#719)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from body.atomic.tool_runner import ToolRunner


# ID: d1e2f3a4-5b6c-4d7e-8f9a-0b1c2d3e4f5a
def test_run_git_builds_correct_argv(tmp_path: Path) -> None:
    with patch("body.atomic.tool_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ToolRunner.run_git(tmp_path, "apply", "--whitespace=nowarn")
        args = mock_run.call_args[0][0]
    assert args == ["git", "-C", str(tmp_path), "apply", "--whitespace=nowarn"]


# ID: e2f3a4b5-6c7d-4e8f-9a0b-1c2d3e4f5a6b
def test_run_git_passes_stdin(tmp_path: Path) -> None:
    with patch("body.atomic.tool_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ToolRunner.run_git(tmp_path, "apply", stdin="--- a/f\n+++ b/f\n")
        _, kwargs = mock_run.call_args
    assert kwargs["input"] == "--- a/f\n+++ b/f\n"


# ID: f3a4b5c6-7d8e-4f9a-0b1c-2d3e4f5a6b7c
def test_run_ruff_returns_true_on_zero_exit(tmp_path: Path) -> None:
    with patch("body.atomic.tool_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert ToolRunner.run_ruff(tmp_path, ["src/foo.py"]) is True


# ID: a4b5c6d7-8e9f-4a0b-1c2d-3e4f5a6b7c8d
def test_run_ruff_returns_false_on_nonzero_exit(tmp_path: Path) -> None:
    with patch("body.atomic.tool_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert ToolRunner.run_ruff(tmp_path, ["src/bad.py"]) is False


# ID: b5c6d7e8-9f0a-4b1c-2d3e-4f5a6b7c8d9e
def test_run_ruff_uses_worktree_as_cwd(tmp_path: Path) -> None:
    with patch("body.atomic.tool_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ToolRunner.run_ruff(tmp_path, ["src/foo.py"])
        _, kwargs = mock_run.call_args
    assert kwargs["cwd"] == str(tmp_path)
