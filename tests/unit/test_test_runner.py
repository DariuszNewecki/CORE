# tests/unit/test_test_runner.py
"""
Tests for the core test execution capability in `core/test_runner.py`.
This ensures that the system's own "immune system" is reliable.
"""
from unittest.mock import MagicMock

import pytest

from core.test_runner import run_tests


@pytest.fixture
def mock_subprocess_run(mocker):
    """Mocks the `subprocess.run` function."""
    return mocker.patch("core.test_runner.subprocess.run")


def test_run_tests_success(mock_subprocess_run):
    """
    Verify that run_tests correctly interprets a successful test run (exit code 0).
    """
    # Arrange: Configure the mock to simulate a successful pytest execution
    mock_subprocess_run.return_value = MagicMock(
        returncode=0,
        stdout="============================= 1 passed in 0.01s =============================",
        stderr="",
    )

    # Act
    result = run_tests()

    # Assert
    assert result["exit_code"] == "0"
    assert result["summary"] == "✅ Tests passed"
    mock_subprocess_run.assert_called_once()


def test_run_tests_failure(mock_subprocess_run):
    """
    Verify that run_tests correctly interprets a failed test run (non-zero exit code).
    """
    # Arrange: Configure the mock to simulate a failed pytest execution
    mock_subprocess_run.return_value = MagicMock(
        returncode=1,
        stdout="============================== 1 failed in 0.01s ==============================",
        stderr="AssertionError: assert False",
    )

    # Act
    result = run_tests()

    # Assert
    assert result["exit_code"] == "1"
    assert result["summary"] == "❌ Tests failed"
    mock_subprocess_run.assert_called_once()


def test_run_tests_pytest_not_found(mock_subprocess_run):
    """
    Verify that run_tests handles the case where pytest is not installed.
    """
    # Arrange: Configure the mock to simulate a FileNotFoundError
    mock_subprocess_run.side_effect = FileNotFoundError(
        "No such file or directory: 'pytest'"
    )

    # Act
    result = run_tests()

    # Assert
    assert result["summary"] == "❌ pytest not found"
    assert "pytest is not installed" in result["stderr"]
    mock_subprocess_run.assert_called_once()
