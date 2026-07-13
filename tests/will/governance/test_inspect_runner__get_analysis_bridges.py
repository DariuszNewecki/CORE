# tests/will/governance/test_inspect_runner__get_analysis_bridges.py

"""Tests for get_analysis_bridges — CodeQL py/stack-trace-exposure fix (#787-adjacent).

Source: src/will/governance/inspect_runner.py
"""

from __future__ import annotations

from unittest.mock import patch

from will.governance.inspect_runner import get_analysis_bridges


def test_returns_generic_error_without_leaking_exception_details() -> None:
    """On failure, the response carries a fixed generic message — not the raw
    exception text — so internal details (paths, implementation specifics)
    never reach an API caller. The real exception is logged server-side."""
    with (
        patch(
            "shared.infrastructure.intent.architecture_bridges.load_bridges",
            side_effect=RuntimeError("/etc/shadow: permission denied"),
        ),
        patch("will.governance.inspect_runner.logger") as mock_logger,
    ):
        result = get_analysis_bridges()

    assert result["available"] is False
    assert result["bridges"] == []
    assert result["error"] == "Failed to load architecture bridges — see server logs."
    assert "/etc/shadow" not in result["error"]
    mock_logger.error.assert_called_once()
    # The real exception text lands in the log call, not the response.
    assert "/etc/shadow" in str(mock_logger.error.call_args)


def test_consuming_filter_uses_bridges_consuming() -> None:
    """When `consuming` is supplied, failures on the filtered lookup path
    also degrade to the generic message."""
    with (
        patch(
            "shared.infrastructure.intent.architecture_bridges.bridges_consuming",
            side_effect=ValueError("boom"),
        ),
        patch("will.governance.inspect_runner.logger"),
    ):
        result = get_analysis_bridges(consuming="AuditFinding")

    assert result["available"] is False
    assert result["error"] == "Failed to load architecture bridges — see server logs."
