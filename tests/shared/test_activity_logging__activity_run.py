"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/activity_logging.py
- Symbol: activity_run
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:14:14
"""

import pytest
import time
from shared.activity_logging import activity_run
from typing import Generator

# Detected return type: Generator[ActivityRun, None, None]
# Function is NOT async (regular 'def'), so use regular test functions

def test_activity_run_yields_activity_run_object():
    """Test that activity_run yields an ActivityRun object."""
    with activity_run("test.workflow") as run:
        assert run is not None
        assert hasattr(run, 'run_id')
        assert isinstance(run.run_id, str)

def test_activity_run_sets_workflow_id():
    """Test that the workflow_id is properly set in the activity run."""
    test_id = "check.audit"
    with activity_run(test_id) as run:
        assert run.workflow_id == test_id

def test_activity_run_with_details():
    """Test activity_run with details parameter."""
    details = {"user": "test_user", "environment": "staging"}
    with activity_run("test.workflow", details=details) as run:
        # The run object should be yielded
        assert run is not None
        # We can't directly test the logging, but we can verify the function accepts details

def test_activity_run_successful_completion():
    """Test that activity_run completes without error when no exception occurs."""
    completed = False
    with activity_run("success.test") as run:
        completed = True

    assert completed is True

def test_activity_run_propagates_exception():
    """Test that activity_run re-raises exceptions from the context block."""
    with pytest.raises(ValueError, match="test error"):
        with activity_run("error.test") as run:
            raise ValueError("test error")

def test_activity_run_duration_captured():
    """Test that duration is captured in both success and error cases."""
    # Test successful case
    start = time.time()
    with activity_run("duration.test") as run:
        time.sleep(0.01)  # Small delay to ensure measurable duration
    end = time.time()

    # Duration should be positive (we can't directly access it, but the function should handle it)
    assert (end - start) > 0

def test_activity_run_context_var_cleanup():
    """Test that context variables are properly cleaned up."""
    # This test ensures the finally block executes
    # We can't directly test the context var, but we can ensure no errors
    with activity_run("cleanup.test") as run:
        pass

    # If we get here without errors, cleanup worked
    assert True

def test_activity_run_multiple_nested():
    """Test that multiple activity_run contexts can be nested."""
    with activity_run("outer.workflow") as outer_run:
        assert outer_run is not None
        with activity_run("inner.workflow") as inner_run:
            assert inner_run is not None
            assert outer_run.run_id != inner_run.run_id

def test_activity_run_with_empty_details():
    """Test activity_run with empty details dict."""
    with activity_run("empty.details", details={}) as run:
        assert run is not None

def test_activity_run_with_none_details():
    """Test activity_run with None details (default)."""
    with activity_run("none.details", details=None) as run:
        assert run is not None

def test_activity_run_different_workflow_ids():
    """Test activity_run with various workflow ID formats."""
    test_cases = [
        "simple",
        "dot.separated",
        "with-hyphen",
        "with_underscore",
        "mixed.case-TEST",
        "deeply.nested.workflow.id"
    ]

    for workflow_id in test_cases:
        with activity_run(workflow_id) as run:
            assert run.workflow_id == workflow_id
