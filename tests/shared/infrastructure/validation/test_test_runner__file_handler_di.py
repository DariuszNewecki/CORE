"""test_runner helper functions — file_handler=None graceful skip (ADR-126 Stage 1).

_log_test_result_to_file and _store_failure_artifact must return immediately
when no FileHandler is injected. These helpers are private but the behavior
is an explicit contract: callers pass None when operating without a write surface.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from shared.infrastructure.validation.test_runner import (
    _log_test_result_to_file,
    _store_failure_artifact,
)


_PASSING_DATA: dict = {
    "exit_code": 0,
    "stdout": "1 passed",
    "stderr": "",
    "summary": "1 passed",
    "error": None,
    "timestamp": "2026-06-26T00:00:00+00:00",
}

_FAILING_DATA: dict = {
    "exit_code": 1,
    "stdout": "",
    "stderr": "AssertionError",
    "summary": "1 failed",
    "error": "1 failed",
    "timestamp": "2026-06-26T00:00:00+00:00",
}


# ID: 2892d135-20cc-4913-bc81-0412b9013679
def test_log_test_result_skips_when_no_file_handler() -> None:
    """_log_test_result_to_file must return without error when file_handler is None."""
    _log_test_result_to_file(_PASSING_DATA, None)


# ID: b1401e8e-b09a-4341-836e-61916b10dcd8
def test_store_failure_artifact_skips_when_no_file_handler() -> None:
    """_store_failure_artifact must return without error when file_handler is None."""
    _store_failure_artifact(_FAILING_DATA, None)


# ID: f6b747aa-e910-4cf6-ad96-4cb1366e75c5
def test_log_test_result_calls_file_handler_when_provided() -> None:
    """_log_test_result_to_file must delegate to file_handler.write_runtime_text."""
    mock_fh = MagicMock()
    _log_test_result_to_file(_PASSING_DATA, mock_fh)
    mock_fh.write_runtime_text.assert_called_once()
    path_arg = mock_fh.write_runtime_text.call_args[0][0]
    assert "tests.jsonl" in path_arg
