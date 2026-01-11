"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/activity_logging.py
- Symbol: ActivityRun
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:13:06
"""

import pytest
from shared.activity_logging import ActivityRun


# ActivityRun is a simple dataclass-like class. It does not contain async methods.
# The class is used to store correlation info.

def test_activityrun_initialization():
    """Test that ActivityRun can be initialized with correct attributes."""
    ar = ActivityRun(workflow_id="test_workflow", run_id="run_123")
    assert ar.workflow_id == "test_workflow"
    assert ar.run_id == "run_123"

def test_activityrun_attribute_access():
    """Test that stored attributes can be accessed correctly."""
    ar = ActivityRun(workflow_id="my_workflow", run_id="id_456")
    assert ar.workflow_id == "my_workflow"
    assert ar.run_id == "id_456"

def test_activityrun_different_values():
    """Test ActivityRun with different string values, including empty strings."""
    ar1 = ActivityRun(workflow_id="", run_id="")
    assert ar1.workflow_id == ""
    assert ar1.run_id == ""

    ar2 = ActivityRun(workflow_id="a", run_id="b")
    assert ar2.workflow_id == "a"
    assert ar2.run_id == "b"

    ar3 = ActivityRun(workflow_id="workflow with spaces", run_id="run with spaces")
    assert ar3.workflow_id == "workflow with spaces"
    assert ar3.run_id == "run with spaces"
