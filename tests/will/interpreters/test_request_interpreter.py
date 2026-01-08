# tests/will/interpreters/test_request_interpreter.py

"""
Tests for RequestInterpreter and subclasses.

Verifies that interpreters correctly parse various inputs into TaskStructure.
"""

import pytest

from will.interpreters import (
    CLIArgsInterpreter,
    NaturalLanguageInterpreter,
    TaskType,
)


class TestNaturalLanguageInterpreter:
    """Test natural language → TaskStructure interpretation."""

    @pytest.mark.asyncio
    async def test_refactor_intent(self):
        """Test refactoring intent recognition."""
        interpreter = NaturalLanguageInterpreter()

        result = await interpreter.execute(
            user_message="refactor UserService for clarity"
        )

        assert result.ok
        task = result.data["task"]
        assert task.task_type == TaskType.REFACTOR
        assert "UserService" in task.targets
        assert task.confidence > 0.5

    @pytest.mark.asyncio
    async def test_fix_intent(self):
        """Test fix intent recognition."""
        interpreter = NaturalLanguageInterpreter()

        result = await interpreter.execute(
            user_message="fix the bug in src/models/user.py"
        )

        assert result.ok
        task = result.data["task"]
        assert task.task_type == TaskType.FIX
        assert "src/models/user.py" in task.targets

    @pytest.mark.asyncio
    async def test_generate_tests_intent(self):
        """Test test generation intent recognition."""
        interpreter = NaturalLanguageInterpreter()

        result = await interpreter.execute(
            user_message="generate tests for ContextBuilder"
        )

        assert result.ok
        task = result.data["task"]
        assert task.task_type == TaskType.TEST
        assert "ContextBuilder" in task.targets

    @pytest.mark.asyncio
    async def test_query_intent(self):
        """Test information query intent recognition."""
        interpreter = NaturalLanguageInterpreter()

        result = await interpreter.execute(user_message="what does FileAnalyzer do?")

        assert result.ok
        task = result.data["task"]
        assert task.task_type == TaskType.QUERY
        assert "FileAnalyzer" in task.targets

    @pytest.mark.asyncio
    async def test_write_constraint_extraction(self):
        """Test constraint extraction from message."""
        interpreter = NaturalLanguageInterpreter()

        # Explicit write mode
        result = await interpreter.execute(
            user_message="refactor UserService and write the changes"
        )
        task = result.data["task"]
        assert task.constraints.get("write") is True

        # Dry run mode
        result = await interpreter.execute(
            user_message="refactor UserService but don't write"
        )
        task = result.data["task"]
        assert task.constraints.get("write") is False

    @pytest.mark.asyncio
    async def test_strategy_hint_extraction(self):
        """Test strategy hint extraction."""
        interpreter = NaturalLanguageInterpreter()

        result = await interpreter.execute(
            user_message="generate unit tests for User model"
        )

        task = result.data["task"]
        assert task.constraints.get("strategy_hint") == "unit_tests"

    @pytest.mark.asyncio
    async def test_unknown_intent_low_confidence(self):
        """Test unknown intent gets low confidence."""
        interpreter = NaturalLanguageInterpreter()

        result = await interpreter.execute(user_message="do something weird")

        assert result.ok
        task = result.data["task"]
        assert task.task_type == TaskType.UNKNOWN
        assert task.confidence < 0.6


class TestCLIArgsInterpreter:
    """Test CLI args → TaskStructure interpretation."""

    @pytest.mark.asyncio
    async def test_fix_clarity_command(self):
        """Test fix clarity CLI command interpretation."""
        interpreter = CLIArgsInterpreter()

        result = await interpreter.execute(
            command="fix",
            subcommand="clarity",
            targets=["src/models/user.py"],
            write=True,
        )

        assert result.ok
        task = result.data["task"]
        assert task.task_type == TaskType.FIX
        assert "src/models/user.py" in task.targets
        assert task.constraints["write"] is True
        assert task.confidence == 1.0  # CLI args are always high confidence

    @pytest.mark.asyncio
    async def test_generate_tests_command(self):
        """Test test generation CLI command interpretation."""
        interpreter = CLIArgsInterpreter()

        result = await interpreter.execute(
            command="coverage",
            subcommand="generate-adaptive",
            targets=["src/analyzers/file_analyzer.py"],
            write=False,
        )

        assert result.ok
        task = result.data["task"]
        assert task.task_type == TaskType.TEST
        assert "src/analyzers/file_analyzer.py" in task.targets

    @pytest.mark.asyncio
    async def test_develop_command(self):
        """Test develop command interpretation."""
        interpreter = CLIArgsInterpreter()

        result = await interpreter.execute(
            command="develop", targets=["add user authentication"], write=True
        )

        assert result.ok
        task = result.data["task"]
        assert task.task_type == TaskType.DEVELOP


class TestTaskStructure:
    """Test TaskStructure data class."""

    def test_task_structure_creation(self):
        """Test creating TaskStructure."""
        from will.interpreters import TaskStructure

        task = TaskStructure(
            task_type=TaskType.REFACTOR,
            intent="refactor UserService",
            targets=["src/services/user.py"],
            constraints={"write": True},
            context={"source": "test"},
            confidence=0.8,
        )

        assert task.task_type == TaskType.REFACTOR
        assert task.intent == "refactor UserService"
        assert len(task.targets) == 1
        assert task.confidence == 0.8
