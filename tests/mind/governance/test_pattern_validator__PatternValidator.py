"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/pattern_validator.py
- Symbol: PatternValidator
- Status: 11 tests passed, some failed
- Passing tests: test_validate_syntax_error, test_validate_command_inspect_pattern, test_validate_command_action_pattern, test_validate_command_check_pattern, test_validate_service_stateful_pattern, test_validate_service_repository_pattern, test_validate_agent_cognitive_pattern, test_validate_with_patterns_loaded, test_validate_with_non_ending_pattern_id, test_validate_empty_code, test_init_with_missing_patterns_dir
- Generated: 2026-01-11 01:45:04
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from mind.governance.pattern_validator import (
    PatternValidationResult,
    PatternValidator,
)


@pytest.mark.asyncio
async def test_validate_syntax_error():
    """Test validation with syntactically invalid code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        invalid_code = "def invalid_syntax:"
        result = await validator.validate(invalid_code, "inspect_pattern", "command")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "syntax_error"
        assert result.violations[0].severity == "error"
        assert result.pattern_id == "inspect_pattern"


@pytest.mark.asyncio
async def test_validate_command_inspect_pattern():
    """Test inspect pattern validation for commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        valid_code = "\ndef inspect_something(read_only=True):\n    pass\n"
        result = await validator.validate(valid_code, "inspect_pattern", "command")
        assert result.passed
        assert len(result.violations) == 0
        invalid_code = "\ndef inspect_something(write=False):\n    pass\n"
        result = await validator.validate(invalid_code, "inspect_pattern", "command")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "forbidden_parameter"
        assert "must not have --write flag" in result.violations[0].message


@pytest.mark.asyncio
async def test_validate_command_action_pattern():
    """Test action pattern validation for commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        valid_code = "\ndef action_something(write=False):\n    pass\n"
        result = await validator.validate(valid_code, "action_pattern", "command")
        assert result.passed
        assert len(result.violations) == 0
        invalid_code = "\ndef action_something():\n    pass\n"
        result = await validator.validate(invalid_code, "action_pattern", "command")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "missing_parameter"
        invalid_code2 = "\ndef action_something(write=True):\n    pass\n"
        result = await validator.validate(invalid_code2, "action_pattern", "command")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "unsafe_default"


@pytest.mark.asyncio
async def test_validate_command_check_pattern():
    """Test check pattern validation for commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        valid_code = "\ndef check_something():\n    pass\n"
        result = await validator.validate(valid_code, "check_pattern", "command")
        assert result.passed
        assert len(result.violations) == 0
        invalid_code = "\ndef check_something(write=False):\n    pass\n"
        result = await validator.validate(invalid_code, "check_pattern", "command")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "forbidden_parameter"


@pytest.mark.asyncio
async def test_validate_service_stateful_pattern():
    """Test stateful service pattern validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        valid_code = "\nclass StatefulService:\n    def __init__(self, dependency):\n        self.dependency = dependency\n"
        result = await validator.validate(valid_code, "stateful_service", "service")
        assert result.passed
        assert len(result.violations) == 0
        warning_code = (
            "\nclass StatefulService:\n    def some_method(self):\n        pass\n"
        )
        result = await validator.validate(warning_code, "stateful_service", "service")
        assert result.passed
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "missing_init"
        assert result.violations[0].severity == "warning"


@pytest.mark.asyncio
async def test_validate_service_repository_pattern():
    """Test repository pattern validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        valid_code = "\nclass UserRepository:\n    def save(self, entity):\n        pass\n    def find_by_id(self, id):\n        pass\n"
        result = await validator.validate(valid_code, "repository_pattern", "service")
        assert result.passed
        assert len(result.violations) == 0
        warning_code = (
            "\nclass UserRepository:\n    def custom_method(self):\n        pass\n"
        )
        result = await validator.validate(warning_code, "repository_pattern", "service")
        assert result.passed
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "missing_standard_methods"
        assert result.violations[0].severity == "warning"


@pytest.mark.asyncio
async def test_validate_agent_cognitive_pattern():
    """Test cognitive agent pattern validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        valid_code = (
            "\nclass CognitiveAgent:\n    def execute(self, task):\n        pass\n"
        )
        result = await validator.validate(valid_code, "cognitive_agent", "agent")
        assert result.passed
        assert len(result.violations) == 0
        invalid_code = (
            "\nclass CognitiveAgent:\n    def run(self, task):\n        pass\n"
        )
        result = await validator.validate(invalid_code, "cognitive_agent", "agent")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "missing_execute"
        assert result.violations[0].severity == "error"


@pytest.mark.asyncio
async def test_validate_with_patterns_loaded():
    """Test validation when patterns are loaded from YAML files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        patterns_dir = repo_root / ".intent" / "charter" / "patterns"
        patterns_dir.mkdir(parents=True)
        pattern_file = patterns_dir / "test_patterns.yaml"
        pattern_data = {
            "id": "test_category",
            "patterns": {"test_pattern": {"description": "Test pattern"}},
        }
        with open(pattern_file, "w") as f:  # noqa: ASYNC230
            yaml.dump(pattern_data, f)
        validator = PatternValidator(repo_root)
        code = "\ndef test_function():\n    pass\n"
        result = await validator.validate(code, "inspect_pattern", "command")
        assert isinstance(result, PatternValidationResult)


@pytest.mark.asyncio
async def test_validate_with_non_ending_pattern_id():
    """Test validation with pattern_id that doesn't end with '_pattern'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        code = "\ndef some_function():\n    pass\n"
        result = await validator.validate(code, "custom_pattern", "command")
        assert isinstance(result, PatternValidationResult)
        assert result.pattern_id == "custom_pattern"


@pytest.mark.asyncio
async def test_validate_empty_code():
    """Test validation with empty code string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        result = await validator.validate("", "inspect_pattern", "command")
        assert result.passed
        assert len(result.violations) == 0


def test_init_with_missing_patterns_dir():
    """Test PatternValidator initialization with missing patterns directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        validator = PatternValidator(repo_root)
        assert validator.patterns == {}
        assert validator.repo_root == repo_root
