"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_types.py
- Symbol: WorkflowRun
- Status: 1 tests passed, some failed
- Passing tests: test_workflow_run_initialization
- Generated: 2026-01-11 00:55:23
"""

from shared.cli_types import WorkflowRun


def test_workflow_run_initialization():
    """Test basic initialization with workflow name."""
    run = WorkflowRun(workflow_name="test.workflow")
    assert run.workflow_name == "test.workflow"
    assert run.results == []
    assert run.ok is True
    assert run.total_duration == 0.0
