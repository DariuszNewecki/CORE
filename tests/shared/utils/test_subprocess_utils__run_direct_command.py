"""Tests for ``run_direct_command`` (ADR-159 Notes: Unit D formatter-runtime
correction).

Root cause it exists to close: ``run_poetry_command`` prefixes every
invocation with ``poetry run``, so a caller whose ``allowed_returncodes``
tolerates the wrapped tool's non-zero "findings" exit (ruff's ``1``) also
silently tolerates *Poetry's own* project-discovery failure sharing that
same exit code -- observed against an external target with no
``pyproject.toml``: Poetry died before ruff ever ran, but the false-success
result propagated through fix.format as ``ok: True`` with zero mutation.
``run_direct_command`` removes Poetry from the launch path entirely, so any
returned exit code unambiguously belongs to the resolved executable.

These tests mirror the structure of
``test_subprocess_utils__run_poetry_command.py`` (mocked subprocess.run)
plus the specific properties this helper adds: no ``poetry run`` prefix,
and a hard failure before any subprocess spawns when the executable is
unresolvable.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from shared.utils.subprocess_utils import (
    SubprocessCommandError,
    SubprocessResult,
    run_direct_command,
)


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    """Stand-in for ``subprocess.CompletedProcess``."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_direct_command_contains_no_poetry_run() -> None:
    """The launched command is exactly [resolved_path, *args] -- no 'poetry',
    no 'run' token anywhere in it."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which",
            return_value="/usr/local/bin/ruff",
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(0, stdout="ok"),
        ) as mock_run,
    ):
        run_direct_command("desc", "ruff", ["format", "package/example.py"])

    launched_command = mock_run.call_args.args[0]
    assert launched_command == ["/usr/local/bin/ruff", "format", "package/example.py"]
    assert "poetry" not in launched_command
    assert "run" not in launched_command


def test_missing_executable_fails_before_execution() -> None:
    """Unresolvable executable raises before subprocess.run is ever called."""
    with (
        patch("shared.utils.subprocess_utils.shutil.which", return_value=None),
        patch("shared.utils.subprocess_utils.subprocess.run") as mock_run,
    ):
        with pytest.raises(SubprocessCommandError) as excinfo:
            run_direct_command("desc", "ruff", ["format", "x.py"])

    assert "ruff executable not found" in str(excinfo.value)
    mock_run.assert_not_called()


def test_exit_one_is_an_allowed_finding_result() -> None:
    """Ruff exit 1 (would-reformat) is not a failure when declared allowed --
    and unlike run_poetry_command, this exit code unambiguously belongs to
    ruff itself, never to a project-manager wrapper."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/ruff"
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(1, stdout="Would reformat: x.py"),
        ),
    ):
        result = run_direct_command(
            "desc", "ruff", ["format", "--check", "x.py"], allowed_returncodes=(0, 1)
        )
    assert isinstance(result, SubprocessResult)
    assert result.returncode == 1
    assert result.stdout == "Would reformat: x.py"


def test_exit_two_or_more_fails() -> None:
    """A genuine tool error (exit >= 2) raises and carries captured stderr."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/ruff"
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(2, stderr="ruff: invalid rule selector 'ZZZ'"),
        ),
    ):
        with pytest.raises(SubprocessCommandError) as excinfo:
            run_direct_command(
                "desc", "ruff", ["check", "x.py"], allowed_returncodes=(0, 1)
            )
    msg = str(excinfo.value)
    assert "exit 2" in msg
    assert "invalid rule selector" in msg
    assert excinfo.value.exit_code == 2


def test_exit_zero_returns_result() -> None:
    """The success path returns a populated SubprocessResult."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/ruff"
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(0, stdout="ok"),
        ),
    ):
        result = run_direct_command("desc", "ruff", ["format", "src/"])
    assert result.returncode == 0
    assert result.stdout == "ok"


def test_cwd_is_passed_through_for_config_discovery() -> None:
    """cwd reaches subprocess.run unchanged, so the launched tool's own
    upward config search (ruff.toml / pyproject.toml / .ruff.toml) is
    preserved -- this helper only changes how the process launches, not
    where it looks for configuration."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/ruff"
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(0),
        ) as mock_run,
    ):
        run_direct_command("desc", "ruff", ["format", "x.py"], cwd="/tmp/sandbox-abc")
    assert mock_run.call_args.kwargs["cwd"] == "/tmp/sandbox-abc"
