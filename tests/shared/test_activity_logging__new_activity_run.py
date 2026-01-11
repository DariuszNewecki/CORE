"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/activity_logging.py
- Symbol: new_activity_run
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:13:14
"""

from shared.activity_logging import new_activity_run


# Detected return type: ActivityRun


def test_new_activity_run_creates_object_with_correct_workflow_id():
    workflow_id = "test_workflow_123"
    result = new_activity_run(workflow_id)
    assert result.workflow_id == workflow_id


def test_new_activity_run_generates_unique_run_ids():
    workflow_id = "same_workflow"
    run1 = new_activity_run(workflow_id)
    run2 = new_activity_run(workflow_id)
    assert run1.run_id != run2.run_id
    assert isinstance(run1.run_id, str)
    assert isinstance(run2.run_id, str)


def test_new_activity_run_returns_activity_run_instance():
    from shared.activity_logging import ActivityRun

    result = new_activity_run("any_id")
    assert isinstance(result, ActivityRun)
