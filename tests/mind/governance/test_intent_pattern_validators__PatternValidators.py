"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/intent_pattern_validators.py
- Symbol: PatternValidators
- Status: 16 tests passed, some failed
- Passing tests: test_validate_inspect_pattern_no_violations, test_validate_inspect_pattern_with_forbidden_params, test_validate_inspect_pattern_multiple_forbidden_params, test_validate_action_pattern_valid, test_validate_action_pattern_missing_write, test_validate_action_pattern_write_defaults_true, test_validate_check_pattern_valid, test_validate_check_pattern_with_write_param, test_validate_check_pattern_with_apply_param, test_validate_run_pattern_valid, test_validate_run_pattern_valid_write_equals, test_validate_run_pattern_missing_write, test_validate_inspect_pattern_edge_case_empty_string, test_validate_action_pattern_edge_case_write_in_comment, test_validate_check_pattern_edge_case_write_in_string, test_path_parameter_usage
- Generated: 2026-01-11 01:36:09
"""

import pytest
from mind.governance.intent_pattern_validators import PatternValidators

def test_validate_inspect_pattern_no_violations():
    """Test inspect pattern with valid read-only code."""
    code = 'def inspect_something(param1: str):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_inspect_pattern(code, target_path)
    assert violations == []

def test_validate_inspect_pattern_with_forbidden_params():
    """Test inspect pattern with forbidden parameters."""
    code = 'def inspect_something(param1: str, write: bool = False):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_inspect_pattern(code, target_path)
    assert len(violations) == 1
    assert violations[0].rule_name == 'inspect_pattern_violation'
    assert violations[0].path == target_path
    assert "Found forbidden parameter 'write:'" in violations[0].message
    assert violations[0].severity == 'error'

def test_validate_inspect_pattern_multiple_forbidden_params():
    """Test inspect pattern with multiple forbidden parameters."""
    code = 'def inspect_something(param1: str, --write, --apply):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_inspect_pattern(code, target_path)
    assert len(violations) == 2
    violation_messages = [v.message for v in violations]
    assert any(('--write' in msg for msg in violation_messages))
    assert any(('--apply' in msg for msg in violation_messages))

def test_validate_action_pattern_valid():
    """Test action pattern with valid write parameter."""
    code = 'def action_something(param1: str, write: bool = False):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_action_pattern(code, target_path)
    assert violations == []

def test_validate_action_pattern_missing_write():
    """Test action pattern missing write parameter."""
    code = 'def action_something(param1: str):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_action_pattern(code, target_path)
    assert len(violations) == 1
    assert violations[0].rule_name == 'action_pattern_violation'
    assert "Missing required 'write' parameter" in violations[0].message
    assert violations[0].severity == 'error'

def test_validate_action_pattern_write_defaults_true():
    """Test action pattern with write defaulting to True."""
    code = 'def action_something(param1: str, write: bool = True):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_action_pattern(code, target_path)
    assert len(violations) == 1
    assert violations[0].rule_name == 'action_pattern_violation'
    assert 'write parameter must default to False' in violations[0].message

def test_validate_check_pattern_valid():
    """Test check pattern with valid non-modifying code."""
    code = 'def check_something(param1: str):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_check_pattern(code, target_path)
    assert violations == []

def test_validate_check_pattern_with_write_param():
    """Test check pattern with write parameter."""
    code = 'def check_something(param1: str, write: bool = False):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_check_pattern(code, target_path)
    assert len(violations) == 1
    assert violations[0].rule_name == 'check_pattern_violation'
    assert 'Check commands must not modify state' in violations[0].message
    assert violations[0].severity == 'error'

def test_validate_check_pattern_with_apply_param():
    """Test check pattern with apply parameter."""
    code = 'def check_something(param1: str, apply: bool = False):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_check_pattern(code, target_path)
    assert len(violations) == 1
    assert 'Check commands must not modify state' in violations[0].message

def test_validate_run_pattern_valid():
    """Test run pattern with write parameter."""
    code = 'def run_something(param1: str, write: bool = False):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_run_pattern(code, target_path)
    assert violations == []

def test_validate_run_pattern_valid_write_equals():
    """Test run pattern with write = False syntax."""
    code = 'def run_something(param1: str, write = False):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_run_pattern(code, target_path)
    assert violations == []

def test_validate_run_pattern_missing_write():
    """Test run pattern missing write parameter."""
    code = 'def run_something(param1: str):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_run_pattern(code, target_path)
    assert len(violations) == 1
    assert violations[0].rule_name == 'run_pattern_violation'
    assert "Missing required 'write' parameter" in violations[0].message
    assert violations[0].severity == 'error'

def test_validate_inspect_pattern_edge_case_empty_string():
    """Test inspect pattern with empty code string."""
    code = ''
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_inspect_pattern(code, target_path)
    assert violations == []

def test_validate_action_pattern_edge_case_write_in_comment():
    """Test action pattern with 'write:' in comment."""
    code = '# This has write: in a comment\ndef action_something(param1: str, write: bool = False):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_action_pattern(code, target_path)
    assert violations == []

def test_validate_check_pattern_edge_case_write_in_string():
    """Test check pattern with 'write:' in string literal."""
    code = 'def check_something(param1: str, message="write:"):'
    target_path = '/full/path/to/file.py'
    violations = PatternValidators.validate_check_pattern(code, target_path)
    assert len(violations) == 1

def test_path_parameter_usage():
    """Test that target_path is correctly passed to ViolationReport."""
    code = 'def inspect_something(write: bool = False):'
    target_path = '/specific/path/to/violating_file.py'
    violations = PatternValidators.validate_inspect_pattern(code, target_path)
    assert len(violations) == 1
    assert violations[0].path == target_path
