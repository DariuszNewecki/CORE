"""Tests for code_style_service.format_code's Ruff invocation shape
(ADR-159 Notes, 2026-09-07: Unit D's final Ruff-runtime correction).

Both the format and check/fix phases must resolve and launch Ruff
directly via run_direct_command -- neither may go through Poetry, since a
governed external target need not have a pyproject.toml of its own. The
format phase was corrected first; the check/fix phase carried the
identical latent defect (reporting complete success while Poetry's own
project-discovery failure silently absorbed the exit code, so ruff never
actually ran) until this correction.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from body.self_healing.code_style_service import format_code
from shared.utils.subprocess_utils import SubprocessCommandError, SubprocessResult


def test_both_phases_use_run_direct_command_with_ruff_no_poetry() -> None:
    """Neither Ruff phase invokes Poetry: both calls resolve/launch 'ruff'
    directly, and neither command list contains a 'poetry' or 'run' token."""
    with patch(
        "body.self_healing.code_style_service.run_direct_command",
        return_value=SubprocessResult(stdout="", stderr="", returncode=0),
    ) as mock_run:
        format_code(path="pkg/mod.py", write=True, cwd="/tmp/sandbox")

    assert mock_run.call_count == 2
    for call in mock_run.call_args_list:
        executable = call.args[1]
        command_args = call.args[2]
        assert executable == "ruff"
        assert "poetry" not in command_args
        assert "run" not in command_args


def test_format_phase_shape() -> None:
    with patch(
        "body.self_healing.code_style_service.run_direct_command",
        return_value=SubprocessResult(stdout="", stderr="", returncode=0),
    ) as mock_run:
        format_code(path="pkg/mod.py", write=True, cwd="/tmp/sandbox")

    format_call = mock_run.call_args_list[0]
    assert format_call.args[2] == ["format", "pkg/mod.py"]
    assert format_call.kwargs["cwd"] == "/tmp/sandbox"
    assert format_call.kwargs["allowed_returncodes"] == (0, 1)


def test_check_fix_phase_shape() -> None:
    with patch(
        "body.self_healing.code_style_service.run_direct_command",
        return_value=SubprocessResult(stdout="", stderr="", returncode=0),
    ) as mock_run:
        format_code(path="pkg/mod.py", write=True, cwd="/tmp/sandbox")

    check_call = mock_run.call_args_list[1]
    assert check_call.args[2] == ["check", "--fix", "--unsafe-fixes", "pkg/mod.py"]
    assert check_call.kwargs["cwd"] == "/tmp/sandbox"
    assert check_call.kwargs["allowed_returncodes"] == (0, 1)


def test_check_only_phase_shape_when_not_writing() -> None:
    with patch(
        "body.self_healing.code_style_service.run_direct_command",
        return_value=SubprocessResult(stdout="", stderr="", returncode=0),
    ) as mock_run:
        format_code(path="pkg/mod.py", write=False, cwd="/tmp/sandbox")

    format_call, check_call = mock_run.call_args_list
    assert format_call.args[2] == ["format", "--check", "pkg/mod.py"]
    assert check_call.args[2] == ["check", "pkg/mod.py"]


def test_missing_ruff_fails_closed() -> None:
    """No installed Ruff -- fails before any phase's subprocess spawns."""
    with patch("shared.utils.subprocess_utils.shutil.which", return_value=None):
        with pytest.raises(SubprocessCommandError, match="ruff executable not found"):
            format_code(path="pkg/mod.py", write=True, cwd="/tmp/sandbox")


def test_genuine_tool_error_fails_closed() -> None:
    """A real Ruff exit >= 2 (genuine tool error, not a findings exit) raises."""
    completed = SimpleNamespace(returncode=2, stdout="", stderr="ruff: fatal error")
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/ruff"
        ),
        patch("shared.utils.subprocess_utils.subprocess.run", return_value=completed),
    ):
        with pytest.raises(SubprocessCommandError) as excinfo:
            format_code(path="pkg/mod.py", write=True, cwd="/tmp/sandbox")
    assert excinfo.value.exit_code == 2
