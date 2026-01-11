"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/activity_logging.py
- Symbol: log_activity
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:13:46
"""

import pytest
from shared.activity_logging import log_activity
from shared.activity_logging import ActivityRun, ActivityStatus

# Detected return type: None (function only logs, returns nothing)
# Detected async status: No 'async def' in target code, use regular test functions


def test_log_activity_basic_workflow_start():
    """Test basic workflow_start event with minimal parameters."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_123")
    # Explicitly set all parameters to avoid side effects from defaults
    log_activity(
        run=run,
        event="workflow_start",
        status=ActivityStatus("info"),
        message=None,
        details=None,
    )


def test_log_activity_with_message_and_details():
    """Test with both message and details provided."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_456")
    details = {"check_count": 5, "duration_ms": 1234}
    log_activity(
        run=run,
        event="check:complete",
        status=ActivityStatus("info"),
        message="All checks completed",
        details=details,
    )


def test_log_activity_workflow_complete_debug_level():
    """Test workflow_complete goes to DEBUG level."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_789")
    log_activity(
        run=run,
        event="workflow_complete",
        status=ActivityStatus("info"),
        message="Workflow finished successfully",
        details=None,
    )


def test_log_activity_phase_event_debug_level():
    """Test phase:* events go to DEBUG level."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_999")
    log_activity(
        run=run,
        event="phase:validation",
        status=ActivityStatus("info"),
        message="Starting validation phase",
        details=None,
    )


def test_log_activity_warning_status():
    """Test warning status triggers WARNING level."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_warn")
    log_activity(
        run=run,
        event="check:warning",
        status=ActivityStatus("warning"),
        message="Potential issue detected",
        details={"issue": "high_memory"},
    )


def test_log_activity_error_status():
    """Test error status triggers ERROR level."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_err")
    log_activity(
        run=run,
        event="check:failed",
        status=ActivityStatus("error"),
        message="Critical failure occurred",
        details={"error_code": "E500", "component": "database"},
    )


def test_log_activity_default_debug_level():
    """Test default DEBUG level for non-special events."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_default")
    log_activity(
        run=run,
        event="custom_event",
        status=ActivityStatus("info"),
        message="Custom event message",
        details=None,
    )


def test_log_activity_no_message_uses_default_format():
    """Test that when message is None, default format is used."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_no_msg")
    log_activity(
        run=run,
        event="step:executed",
        status=ActivityStatus("success"),
        message=None,
        details={"step": "transform_data"},
    )


def test_log_activity_empty_details():
    """Test with empty details dictionary."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_empty")
    log_activity(
        run=run,
        event="check:started",
        status=ActivityStatus("info"),
        message="Starting check",
        details={},
    )


def test_log_activity_complex_details_structure():
    """Test with nested details structure."""
    run = ActivityRun(workflow_id="test_wf", run_id="run_complex")
    details = {
        "results": [
            {"id": 1, "passed": True},
            {"id": 2, "passed": False, "reason": "timeout"}
        ],
        "summary": {"total": 2, "passed": 1, "failed": 1}
    }
    log_activity(
        run=run,
        event="batch:complete",
        status=ActivityStatus("info"),
        message="Batch processing complete",
        details=details,
    )
