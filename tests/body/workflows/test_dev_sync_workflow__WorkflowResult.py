"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/workflows/dev_sync_workflow.py
- Symbol: WorkflowResult
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:32:59
"""

from body.workflows.dev_sync_workflow import WorkflowResult


class TestWorkflowResult:
    """Test suite for WorkflowResult class."""

    def test_ok_property_all_phases_succeed(self):
        """Test ok property when all phases succeed."""
        # Arrange
        phase1 = WorkflowPhase(ok=True, actions=[], duration=1.0)
        phase2 = WorkflowPhase(ok=True, actions=[], duration=2.0)
        result = WorkflowResult(workflow_id="dev.sync", phases=[phase1, phase2])

        # Act & Assert
        assert result.ok

    def test_ok_property_some_phases_fail(self):
        """Test ok property when some phases fail."""
        # Arrange
        phase1 = WorkflowPhase(ok=True, actions=[], duration=1.0)
        phase2 = WorkflowPhase(ok=False, actions=[], duration=2.0)
        result = WorkflowResult(workflow_id="dev.sync", phases=[phase1, phase2])

        # Act & Assert
        assert not result.ok

    def test_ok_property_empty_phases(self):
        """Test ok property when there are no phases."""
        # Arrange
        result = WorkflowResult(workflow_id="dev.sync", phases=[])

        # Act & Assert
        assert result.ok

    def test_total_duration_calculation(self):
        """Test total_duration property calculation."""
        # Arrange
        phase1 = WorkflowPhase(ok=True, actions=[], duration=1.5)
        phase2 = WorkflowPhase(ok=True, actions=[], duration=2.5)
        phase3 = WorkflowPhase(ok=False, actions=[], duration=3.0)
        result = WorkflowResult(workflow_id="dev.sync", phases=[phase1, phase2, phase3])

        # Act & Assert
        assert result.total_duration == 7.0

    def test_total_duration_zero_phases(self):
        """Test total_duration property with no phases."""
        # Arrange
        result = WorkflowResult(workflow_id="dev.sync", phases=[])

        # Act & Assert
        assert result.total_duration == 0.0

    def test_total_actions_calculation(self):
        """Test total_actions property calculation."""
        # Arrange
        action1 = ActionResult(ok=True)
        action2 = ActionResult(ok=False)
        action3 = ActionResult(ok=True)

        phase1 = WorkflowPhase(ok=True, actions=[action1, action2], duration=1.0)
        phase2 = WorkflowPhase(ok=True, actions=[action3], duration=2.0)
        result = WorkflowResult(workflow_id="dev.sync", phases=[phase1, phase2])

        # Act & Assert
        assert result.total_actions == 3

    def test_total_actions_empty_phases(self):
        """Test total_actions property with empty phases."""
        # Arrange
        phase1 = WorkflowPhase(ok=True, actions=[], duration=1.0)
        phase2 = WorkflowPhase(ok=True, actions=[], duration=2.0)
        result = WorkflowResult(workflow_id="dev.sync", phases=[phase1, phase2])

        # Act & Assert
        assert result.total_actions == 0

    def test_failed_actions_all_succeed(self):
        """Test failed_actions property when all actions succeed."""
        # Arrange
        action1 = ActionResult(ok=True)
        action2 = ActionResult(ok=True)

        phase1 = WorkflowPhase(ok=True, actions=[action1], duration=1.0)
        phase2 = WorkflowPhase(ok=True, actions=[action2], duration=2.0)
        result = WorkflowResult(workflow_id="dev.sync", phases=[phase1, phase2])

        # Act & Assert
        assert result.failed_actions == []

    def test_failed_actions_some_fail(self):
        """Test failed_actions property when some actions fail."""
        # Arrange
        action1 = ActionResult(ok=True)
        action2 = ActionResult(ok=False)
        action3 = ActionResult(ok=False)
        action4 = ActionResult(ok=True)

        phase1 = WorkflowPhase(ok=True, actions=[action1, action2], duration=1.0)
        phase2 = WorkflowPhase(ok=False, actions=[action3, action4], duration=2.0)
        result = WorkflowResult(workflow_id="dev.sync", phases=[phase1, phase2])

        # Act
        failed = result.failed_actions

        # Assert
        assert len(failed) == 2
        assert action2 in failed
        assert action3 in failed
        assert action1 not in failed
        assert action4 not in failed

    def test_failed_actions_all_fail(self):
        """Test failed_actions property when all actions fail."""
        # Arrange
        action1 = ActionResult(ok=False)
        action2 = ActionResult(ok=False)

        phase1 = WorkflowPhase(ok=False, actions=[action1], duration=1.0)
        phase2 = WorkflowPhase(ok=False, actions=[action2], duration=2.0)
        result = WorkflowResult(workflow_id="dev.sync", phases=[phase1, phase2])

        # Act & Assert
        assert len(result.failed_actions) == 2
        assert result.failed_actions == [action1, action2]

    def test_failed_actions_empty_phases(self):
        """Test failed_actions property with empty phases."""
        # Arrange
        result = WorkflowResult(workflow_id="dev.sync", phases=[])

        # Act & Assert
        assert result.failed_actions == []

    def test_workflow_id_assignment(self):
        """Test that workflow_id is properly assigned."""
        # Arrange & Act
        result = WorkflowResult(workflow_id="test.workflow", phases=[])

        # Assert
        assert result.workflow_id == "test.workflow"

    def test_phases_default_factory(self):
        """Test that phases uses default_factory for empty list."""
        # Arrange & Act
        result = WorkflowResult(workflow_id="dev.sync")

        # Assert
        assert result.phases == []
        assert isinstance(result.phases, list)


# Mock classes for testing since we don't have the actual implementations
class ActionResult:
    def __init__(self, ok: bool):
        self.ok = ok

    def __eq__(self, other):
        if not isinstance(other, ActionResult):
            return False
        return self.ok == other.ok


class WorkflowPhase:
    def __init__(self, ok: bool, actions: list[ActionResult], duration: float):
        self.ok = ok
        self.actions = actions
        self.duration = duration

    def __eq__(self, other):
        if not isinstance(other, WorkflowPhase):
            return False
        return (
            self.ok == other.ok
            and self.actions == other.actions
            and self.duration == other.duration
        )
