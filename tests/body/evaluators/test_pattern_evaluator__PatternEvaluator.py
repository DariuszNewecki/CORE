"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/evaluators/pattern_evaluator.py
- Symbol: PatternEvaluator
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:18:19
"""

import pytest

from body.evaluators.pattern_evaluator import PatternEvaluator


# PatternEvaluator.execute() is async (starts with 'async def'), so tests must be async too


@pytest.mark.asyncio
async def test_execute_all_category_with_violations(tmp_path):
    """Test execute with category='all' when violations exist."""
    evaluator = PatternEvaluator()

    # Create a test command file with an inspect pattern violation
    commands_dir = tmp_path / "src" / "body" / "cli" / "commands"
    commands_dir.mkdir(parents=True)

    test_file = commands_dir / "test_command.py"
    test_file.write_text(
        '''
def inspect_command(write=False):
    """
    Pattern: inspect
    """
    pass
'''
    )

    result = await evaluator.execute(category="all", repo_root=tmp_path)

    assert not result.ok
    assert result.data["total"] >= 1
    assert result.data["compliant"] >= 0
    assert result.data["compliance_rate"] < 100.0
    assert len(result.data["violations"]) >= 1
    assert result.metadata["category"] == "all"
    assert result.metadata["violation_count"] >= 1
    assert result.phase.value == "audit"
    assert result.confidence == 1.0
    assert result.duration_sec > 0.0


@pytest.mark.asyncio
async def test_execute_specific_category_commands(tmp_path):
    """Test execute with category='commands'."""
    evaluator = PatternEvaluator()

    # Create a test command file
    commands_dir = tmp_path / "src" / "body" / "cli" / "commands"
    commands_dir.mkdir(parents=True)

    test_file = commands_dir / "test_command.py"
    test_file.write_text(
        '''
def action_command(write=False):
    """
    Pattern: action
    """
    pass
'''
    )

    result = await evaluator.execute(category="commands", repo_root=tmp_path)

    assert result.metadata["category"] == "commands"
    # Should return ComponentResult even if no violations


@pytest.mark.asyncio
async def test_execute_unknown_category(tmp_path):
    """Test execute with unknown category returns empty violations."""
    evaluator = PatternEvaluator()

    result = await evaluator.execute(category="unknown", repo_root=tmp_path)

    assert result.ok
    assert result.data["total"] == 1
    assert result.data["compliant"] == 1
    assert result.data["compliance_rate"] == 100.0
    assert result.data["violations"] == []
    assert result.metadata["category"] == "unknown"
    assert result.metadata["violation_count"] == 0


@pytest.mark.asyncio
async def test_execute_no_patterns_directory(tmp_path):
    """Test execute when patterns directory doesn't exist."""
    evaluator = PatternEvaluator()

    result = await evaluator.execute(category="all", repo_root=tmp_path)

    # Should still run checks even without patterns directory
    assert isinstance(result.ok, bool)
    assert "total" in result.data
    assert "compliant" in result.data
    assert "compliance_rate" in result.data
    assert "violations" in result.data


def test_load_patterns_directory_not_exists(tmp_path):
    """Test _load_patterns when directory doesn't exist."""
    evaluator = PatternEvaluator()

    patterns = evaluator._load_patterns(tmp_path)

    assert patterns == {}


def test_load_patterns_with_valid_yaml(tmp_path):
    """Test _load_patterns with valid YAML files."""
    evaluator = PatternEvaluator()

    patterns_dir = tmp_path / ".intent" / "charter" / "patterns"
    patterns_dir.mkdir(parents=True)

    test_pattern = patterns_dir / "command_patterns.yaml"
    test_pattern.write_text(
        """
id: commands
patterns:
  - name: inspect
    description: Read-only commands
"""
    )

    patterns = evaluator._load_patterns(tmp_path)

    assert "commands" in patterns
    assert patterns["commands"]["id"] == "commands"
    assert "patterns" in patterns["commands"]


def test_check_all_calls_all_checkers(tmp_path):
    """Test _check_all calls all checkers."""
    evaluator = PatternEvaluator()

    # Create minimal structure for checkers to run without errors
    (tmp_path / "src" / "body" / "cli" / "commands").mkdir(parents=True, exist_ok=True)

    violations = evaluator._check_all(tmp_path, {})

    assert isinstance(violations, list)
    # All checkers should return empty lists for now


def test_check_category_valid_category(tmp_path):
    """Test _check_category with valid category."""
    evaluator = PatternEvaluator()

    # Create commands directory for the commands checker
    (tmp_path / "src" / "body" / "cli" / "commands").mkdir(parents=True, exist_ok=True)

    violations = evaluator._check_category(tmp_path, {}, "commands")

    assert isinstance(violations, list)


def test_check_category_invalid_category(tmp_path):
    """Test _check_category with invalid category."""
    evaluator = PatternEvaluator()

    violations = evaluator._check_category(tmp_path, {}, "invalid")

    assert violations == []


def test_check_commands_no_directory(tmp_path):
    """Test _check_commands when directory doesn't exist."""
    evaluator = PatternEvaluator()

    violations = evaluator._check_commands(tmp_path)

    assert violations == []


def test_check_command_file_with_inspect_pattern_violation(tmp_path):
    """Test _check_command_file with inspect pattern violation."""
    evaluator = PatternEvaluator()

    test_file = tmp_path / "test.py"
    test_file.write_text(
        '''
def inspect_function(write=True):
    """
    Pattern: inspect
    """
    pass
'''
    )

    violations = evaluator._check_command_file(test_file)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.file_path == str(test_file)
    assert violation.component_name == "inspect_function"
    assert violation.pattern_id == "inspect_pattern"
    assert violation.violation_type == "forbidden_parameter"
    assert "must not have --write flag" in violation.message
    assert violation.severity == "error"
    assert violation.line_number == 2


def test_check_command_file_with_action_pattern_missing_write(tmp_path):
    """Test _check_command_file with action pattern missing write parameter."""
    evaluator = PatternEvaluator()

    test_file = tmp_path / "test.py"
    test_file.write_text(
        '''
def action_function():
    """
    Pattern: action
    """
    pass
'''
    )

    violations = evaluator._check_command_file(test_file)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.pattern_id == "action_pattern"
    assert violation.violation_type == "missing_parameter"
    assert "must have 'write' parameter" in violation.message


def test_check_command_file_with_action_pattern_unsafe_default(tmp_path):
    """Test _check_command_file with action pattern unsafe default."""
    evaluator = PatternEvaluator()

    test_file = tmp_path / "test.py"
    test_file.write_text(
        '''
def action_function(write=True):
    """
    Pattern: action
    """
    pass
'''
    )

    violations = evaluator._check_command_file(test_file)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.pattern_id == "action_pattern"
    assert violation.violation_type == "unsafe_default"
    assert "must default to False" in violation.message


def test_check_command_file_with_check_pattern_violation(tmp_path):
    """Test _check_command_file with check pattern violation."""
    evaluator = PatternEvaluator()

    test_file = tmp_path / "test.py"
    test_file.write_text(
        '''
def check_function(write=False):
    """
    Pattern: check
    """
    pass
'''
    )

    violations = evaluator._check_command_file(test_file)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.pattern_id == "check_pattern"
    assert violation.violation_type == "forbidden_parameter"
    assert "must not modify state" in violation.message


def test_check_command_file_no_pattern_declared(tmp_path):
    """Test _check_command_file with no pattern declared."""
    evaluator = PatternEvaluator()

    test_file = tmp_path / "test.py"
    test_file.write_text(
        '''
def regular_function():
    """No pattern here."""
    pass
'''
    )

    violations = evaluator._check_command_file(test_file)

    assert violations == []


def test_check_command_file_no_docstring(tmp_path):
    """Test _check_command_file with function without docstring."""
    evaluator = PatternEvaluator()

    test_file = tmp_path / "test.py"
    test_file.write_text(
        """
def no_docstring():
    pass
"""
    )

    violations = evaluator._check_command_file(test_file)

    assert violations == []


def test_get_declared_pattern_with_pattern():
    """Test _get_declared_pattern extracts pattern from docstring."""
    evaluator = PatternEvaluator()

    # Create a mock AST node
    import ast

    source = '''
def test():
    """
    Pattern: inspect
    Some description.
    """
    pass
'''
    tree = ast.parse(source)
    node = tree.body[0]

    pattern = evaluator._get_declared_pattern(node)

    assert pattern == "inspect"


def test_get_declared_pattern_no_pattern():
    """Test _get_declared_pattern when no pattern in docstring."""
    evaluator = PatternEvaluator()

    import ast

    source = '''
def test():
    """No pattern here."""
    pass
'''
    tree = ast.parse(source)
    node = tree.body[0]

    pattern = evaluator._get_declared_pattern(node)

    assert pattern is None


def test_get_declared_pattern_no_docstring():
    """Test _get_declared_pattern with no docstring."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    pattern = evaluator._get_declared_pattern(node)

    assert pattern is None


def test_has_parameter_positional():
    """Test _has_parameter finds positional parameter."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(write): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    has_param = evaluator._has_parameter(node, "write")

    assert has_param


def test_has_parameter_keyword_only():
    """Test _has_parameter finds keyword-only parameter."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(*, write): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    has_param = evaluator._has_parameter(node, "write")

    assert has_param


def test_has_parameter_not_found():
    """Test _has_parameter when parameter doesn't exist."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(other): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    has_param = evaluator._has_parameter(node, "write")

    assert not has_param


def test_get_parameter_default_positional_with_default():
    """Test _get_parameter_default for positional parameter with default."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(write=False): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    default = evaluator._get_parameter_default(node, "write")

    assert not default


def test_get_parameter_default_positional_no_default():
    """Test _get_parameter_default for positional parameter without default."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(write): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    default = evaluator._get_parameter_default(node, "write")

    # Should return _NO_DEFAULT sentinel
    from body.evaluators.pattern_evaluator import _NO_DEFAULT

    assert default is _NO_DEFAULT


def test_get_parameter_default_keyword_only_with_default():
    """Test _get_parameter_default for keyword-only parameter with default."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(*, write=False): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    default = evaluator._get_parameter_default(node, "write")

    assert not default


def test_get_parameter_default_keyword_only_no_default():
    """Test _get_parameter_default for keyword-only parameter without default."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(*, write): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    default = evaluator._get_parameter_default(node, "write")

    from body.evaluators.pattern_evaluator import _NO_DEFAULT

    assert default is _NO_DEFAULT


def test_get_parameter_default_parameter_not_found():
    """Test _get_parameter_default when parameter doesn't exist."""
    evaluator = PatternEvaluator()

    import ast

    source = "def test(other): pass"
    tree = ast.parse(source)
    node = tree.body[0]

    default = evaluator._get_parameter_default(node, "write")

    assert default is None


def test_check_services_not_implemented(tmp_path):
    """Test _check_services returns empty list (not implemented)."""
    evaluator = PatternEvaluator()

    violations = evaluator._check_services(tmp_path)

    assert violations == []


def test_check_agents_not_implemented(tmp_path):
    """Test _check_agents returns empty list (not implemented)."""
    evaluator = PatternEvaluator()

    violations = evaluator._check_agents(tmp_path)

    assert violations == []


def test_check_workflows_not_implemented(tmp_path):
    """Test _check_workflows returns empty list (not implemented)."""
    evaluator = PatternEvaluator()

    violations = evaluator._check_workflows(tmp_path)

    assert violations == []
