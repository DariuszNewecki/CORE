"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/workflows/dev_sync_workflow.py
- Symbol: WorkflowPhase
- Status: 9 tests passed, some failed
- Passing tests: test_initialization_with_name, test_ok_property_empty_actions, test_ok_property_all_successful_actions, test_ok_property_with_failed_action, test_duration_property_empty_actions, test_duration_property_with_actions, test_duration_property_mixed_success_failure, test_actions_list_mutability, test_multiple_phases_independence
- Generated: 2026-01-11 03:32:07
"""

from body.workflows.dev_sync_workflow import WorkflowPhase


class TestWorkflowPhase:

    def test_initialization_with_name(self):
        """Test WorkflowPhase initialization with name."""
        phase = WorkflowPhase(name="Test Phase")
        assert phase.name == "Test Phase"
        assert phase.actions == []

    def test_ok_property_empty_actions(self):
        """Test ok property with empty actions list."""
        phase = WorkflowPhase(name="Empty Phase")
        assert phase.ok

    def test_ok_property_all_successful_actions(self):
        """Test ok property when all actions succeed."""

        class MockAction:

            def __init__(self, ok_value):
                self.ok = ok_value
                self.duration_sec = 1.0

        phase = WorkflowPhase(name="Successful Phase")
        phase.actions = [MockAction(True), MockAction(True), MockAction(True)]
        assert phase.ok

    def test_ok_property_with_failed_action(self):
        """Test ok property when at least one action fails."""

        class MockAction:

            def __init__(self, ok_value):
                self.ok = ok_value
                self.duration_sec = 1.0

        phase = WorkflowPhase(name="Failed Phase")
        phase.actions = [MockAction(True), MockAction(False), MockAction(True)]
        assert not phase.ok

    def test_duration_property_empty_actions(self):
        """Test duration property with empty actions list."""
        phase = WorkflowPhase(name="No Actions Phase")
        assert phase.duration == 0.0

    def test_duration_property_with_actions(self):
        """Test duration property with multiple actions."""

        class MockAction:

            def __init__(self, duration):
                self.ok = True
                self.duration_sec = duration

        phase = WorkflowPhase(name="Duration Test Phase")
        phase.actions = [MockAction(1.5), MockAction(2.0), MockAction(0.5)]
        assert phase.duration == 4.0

    def test_duration_property_mixed_success_failure(self):
        """Test duration property includes all actions regardless of success."""

        class MockAction:

            def __init__(self, ok_value, duration):
                self.ok = ok_value
                self.duration_sec = duration

        phase = WorkflowPhase(name="Mixed Phase")
        phase.actions = [
            MockAction(True, 1.0),
            MockAction(False, 2.5),
            MockAction(True, 0.5),
        ]
        assert phase.duration == 4.0

    def test_actions_list_mutability(self):
        """Test that actions list can be modified after initialization."""
        phase = WorkflowPhase(name="Mutable Phase")
        assert phase.actions == []

        class MockAction:

            def __init__(self):
                self.ok = True
                self.duration_sec = 1.0

        action = MockAction()
        phase.actions.append(action)
        assert len(phase.actions) == 1
        assert phase.actions[0] == action

    def test_multiple_phases_independence(self):
        """Test that multiple phases don't share action lists."""
        phase1 = WorkflowPhase(name="Phase 1")
        phase2 = WorkflowPhase(name="Phase 2")

        class MockAction:

            def __init__(self):
                self.ok = True
                self.duration_sec = 1.0

        action = MockAction()
        phase1.actions.append(action)
        assert len(phase1.actions) == 1
        assert len(phase2.actions) == 0
        assert phase2.actions == []
