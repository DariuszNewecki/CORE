"""Regression tests for ``run_poetry_command`` exit-code handling (#660).

The bug: ``run_poetry_command`` used ``subprocess.run(check=True)``, so *any*
non-zero exit raised ``SubprocessCommandError("poetry command failed.")``. But
the tools it wraps use a non-zero exit to report *findings*, not execution
failure — ruff returns ``1`` for "would reformat" / lint findings, reserving
``2`` for a genuine error. Every formattable file therefore failed ``fix.format``
with the opaque "poetry command failed.", and the real stderr was discarded
(logged to the ephemeral daemon log only, never persisted).

These tests pin: (1) findings exit codes the caller declares allowed do not
raise, (2) disallowed exits still raise AND carry the captured stderr, and
(3) the success path returns a populated ``SubprocessResult``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from shared.utils.subprocess_utils import (
    SubprocessCommandError,
    SubprocessResult,
    run_poetry_command,
)


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    """Stand-in for ``subprocess.CompletedProcess``."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_exit_zero_returns_result() -> None:
    """The success path returns a populated SubprocessResult."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/poetry"
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(0, stdout="ok"),
        ),
    ):
        result = run_poetry_command("desc", ["ruff", "format", "src/"])
    assert isinstance(result, SubprocessResult)
    assert result.returncode == 0
    assert result.stdout == "ok"


def test_findings_exit_does_not_raise_when_allowed() -> None:
    """#660 core fix: ruff exit 1 (would reformat / lint findings) is NOT a
    failure when the caller declares it allowed."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/poetry"
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(1, stdout="Would reformat: x.py"),
        ),
    ):
        result = run_poetry_command(
            "desc", ["ruff", "format", "--check", "x.py"], allowed_returncodes=(0, 1)
        )
    assert result.returncode == 1  # no exception — this is the regression guard


def test_findings_exit_still_raises_under_default_allowed() -> None:
    """With the default ``allowed_returncodes=(0,)`` a non-zero exit raises —
    the negative control that pins the allow-list to the caller's declaration."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/poetry"
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(1, stderr="boom"),
        ),
        pytest.raises(SubprocessCommandError),
    ):
        run_poetry_command("desc", ["ruff", "format", "--check", "x.py"])


def test_real_error_raises_and_carries_stderr() -> None:
    """A disallowed exit (ruff exit 2 = genuine error) raises AND the captured
    stderr is threaded into the message so the failure is diagnosable from the
    persisted record, not only the daemon log (#660 secondary defect)."""
    with (
        patch(
            "shared.utils.subprocess_utils.shutil.which", return_value="/usr/bin/poetry"
        ),
        patch(
            "shared.utils.subprocess_utils.subprocess.run",
            return_value=_completed(2, stderr="ruff: invalid rule selector 'ZZZ'"),
        ),
    ):
        with pytest.raises(SubprocessCommandError) as excinfo:
            run_poetry_command(
                "desc", ["ruff", "check", "x.py"], allowed_returncodes=(0, 1)
            )
    msg = str(excinfo.value)
    assert "exit 2" in msg
    assert "invalid rule selector" in msg  # stderr is preserved, not discarded
    assert excinfo.value.exit_code == 2


def test_missing_poetry_executable_raises() -> None:
    """Absent poetry on PATH raises a distinct, clear error."""
    with patch("shared.utils.subprocess_utils.shutil.which", return_value=None):
        with pytest.raises(SubprocessCommandError) as excinfo:
            run_poetry_command("desc", ["ruff", "format", "src/"])
    assert "executable not found" in str(excinfo.value)
