import pytest
from pydantic import ValidationError

from shared.models.execution_models import (
    ExecutionTask,
    PlanExecutionError,
    PlannerConfig,
    TaskParams,
)


class TestExecutionTask:
    """Tests for ExecutionTask model."""

    def test_valid_default_task_type(self):
        """Test that a valid task_type (default) passes validation."""
        task = ExecutionTask(step="step_1", action="test_action", params=TaskParams())
        assert task.task_type == "code_generation"
        assert task.step == "step_1"
        assert task.action == "test_action"
        assert task.params == TaskParams()

    def test_invalid_task_type_raises_error(self):
        """Test that an invalid task_type raises a ValidationError."""
        with pytest.raises(ValidationError) as excinfo:
            ExecutionTask(
                step="step_1",
                action="test_action",
                params=TaskParams(),
                task_type="invalid_task_type",
            )
        assert "Invalid task_type" in str(excinfo.value)

    def test_params_required(self):
        """params is a required field — the autogen vintage assumed it
        defaulted to ``TaskParams()`` when omitted, but the current
        ExecutionTask schema makes it explicit (Pydantic v2 ``Field``
        with no default). Omitting it raises ValidationError; the
        canonical empty-params shape is ``params=TaskParams()``."""
        with pytest.raises(ValidationError):
            ExecutionTask(step="step_1", action="test_action")
        # And: explicitly providing an empty TaskParams works.
        task = ExecutionTask(step="step_1", action="test_action", params=TaskParams())
        assert isinstance(task.params, TaskParams)

    def test_step_required(self):
        """Test that step is a required field."""
        with pytest.raises(ValidationError):
            ExecutionTask(action="test_action", params=TaskParams())

    def test_action_required(self):
        """Test that action is a required field."""
        with pytest.raises(ValidationError):
            ExecutionTask(step="step_1", params=TaskParams())


class TestPlanExecutionError:
    """Tests for PlanExecutionError exception."""

    def test_default_violations_empty(self):
        """Test that violations defaults to empty list."""
        error = PlanExecutionError("some error")
        assert error.violations == []

    def test_violations_provided(self):
        """Test that violations are stored."""
        violations = [{"type": "failure", "detail": "something went wrong"}]
        error = PlanExecutionError("error", violations=violations)
        assert error.violations == violations

    def test_message_stored(self):
        """Test that message is stored in the exception."""
        error = PlanExecutionError("test message")
        assert str(error) == "test message"

    def test_violations_none_becomes_empty(self):
        """Test that None violations become empty list."""
        error = PlanExecutionError("msg", violations=None)
        assert error.violations == []


class TestPlannerConfig:
    """Tests for PlannerConfig model."""

    def test_default_values(self):
        """Test default values for PlannerConfig fields."""
        config = PlannerConfig()
        assert config.rollback_on_failure is True
        assert config.auto_commit is True
        # task_timeout has default_factory, so it should be an int
        assert isinstance(config.task_timeout, int)

    def test_rollback_on_failure_setting(self):
        """Test rollback_on_failure can be set to False."""
        config = PlannerConfig(rollback_on_failure=False)
        assert config.rollback_on_failure is False

    def test_auto_commit_setting(self):
        """Test auto_commit can be set to False."""
        config = PlannerConfig(auto_commit=False)
        assert config.auto_commit is False


class TestTaskParams:
    """Tests for TaskParams model."""

    def test_default_values(self):
        """Test that all fields default to None."""
        params = TaskParams()
        assert params.file_path is None
        assert params.code is None
        assert params.symbol_name is None
        assert params.justification is None
        assert params.tag is None

    def test_set_file_path(self):
        """Test setting file_path."""
        params = TaskParams(file_path="/path/to/file.py")
        assert params.file_path == "/path/to/file.py"

    def test_set_code(self):
        """Test setting code."""
        params = TaskParams(code="print('hello')")
        assert params.code == "print('hello')"

    def test_set_symbol_name(self):
        """Test setting symbol_name."""
        params = TaskParams(symbol_name="MyClass")
        assert params.symbol_name == "MyClass"

    def test_set_justification(self):
        """Test setting justification."""
        params = TaskParams(justification="necessary refactor")
        assert params.justification == "necessary refactor"

    def test_set_tag(self):
        """Test setting tag."""
        params = TaskParams(tag="v1.2")
        assert params.tag == "v1.2"

    def test_partial_fields(self):
        """Test that only some fields can be provided."""
        params = TaskParams(file_path="/tmp/code.py", tag="test")
        assert params.file_path == "/tmp/code.py"
        assert params.tag == "test"
        assert params.code is None
        assert params.symbol_name is None
        assert params.justification is None
