# tests/shared/utils/test_subprocess_utils.py
"""Tests for subprocess_utils module."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import typer

from shared.utils.subprocess_utils import run_poetry_command


class TestRunPoetryCommand:
    """Tests for run_poetry_command function."""

    def test_successful_command_execution(self, capsys):
        """Test successful command execution with stdout."""
        with patch("shutil.which", return_value="/usr/bin/poetry"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="Success output", stderr="", returncode=0
                )

                run_poetry_command("Test command", ["pytest"])

                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert call_args[0] == "/usr/bin/poetry"
                assert call_args[1] == "run"
                assert "pytest" in call_args

    def test_command_with_stderr(self):
        """Test command execution with stderr output."""
        with patch("shutil.which", return_value="/usr/bin/poetry"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="", stderr="Warning message", returncode=0
                )

                run_poetry_command("Test command", ["test"])

                mock_run.assert_called_once()

    def test_poetry_not_found_raises_exit(self):
        """Test that missing poetry executable raises typer.Exit."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(typer.Exit) as exc_info:
                run_poetry_command("Test", ["pytest"])

            assert exc_info.value.exit_code == 1

    def test_command_failure_raises_exit(self):
        """Test that failed command raises typer.Exit."""
        with patch("shutil.which", return_value="/usr/bin/poetry"):
            with patch("subprocess.run") as mock_run:
                error = subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["poetry", "run", "pytest"],
                    output="",
                    stderr="Error message",
                )
                error.stdout = "Command output"
                error.stderr = "Error details"
                mock_run.side_effect = error

                with pytest.raises(typer.Exit) as exc_info:
                    run_poetry_command("Test", ["pytest"])

                assert exc_info.value.exit_code == 1

    def test_multiple_command_arguments(self):
        """Test command with multiple arguments."""
        with patch("shutil.which", return_value="/usr/bin/poetry"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

                run_poetry_command("Test", ["pytest", "-v", "--tb=short"])

                call_args = mock_run.call_args[0][0]
                assert call_args[-3:] == ["pytest", "-v", "--tb=short"]

    def test_empty_stdout_stderr(self):
        """Test command with no output."""
        with patch("shutil.which", return_value="/usr/bin/poetry"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

                run_poetry_command("Test", ["test"])

                mock_run.assert_called_once()
