"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/services/validation/validation_policies.py
- Symbol: PolicyValidator
- Status: 15 tests passed, some failed
- Passing tests: test_policy_validator_initialization, test_get_full_attribute_name_simple, test_get_full_attribute_name_nested, test_get_full_attribute_name_single_attribute, test_find_dangerous_patterns_forbidden_call, test_find_dangerous_patterns_excluded_file, test_find_dangerous_patterns_non_excluded_file, test_find_dangerous_patterns_mixed_rules, test_find_dangerous_patterns_attribute_call, test_find_dangerous_patterns_no_violations, test_check_semantics_valid_code, test_check_semantics_syntax_error, test_check_semantics_empty_code, test_find_dangerous_patterns_line_numbers, test_find_dangerous_patterns_import_from_no_module
- Generated: 2026-01-11 03:36:24
"""

import pytest
import ast
from pathlib import Path
from body.services.validation.validation_policies import PolicyValidator

def test_policy_validator_initialization():
    """Test that PolicyValidator initializes with safety rules."""
    safety_rules = [{'id': 'test_rule', 'detection': {'patterns': []}}]
    validator = PolicyValidator(safety_rules)
    assert validator.safety_rules == safety_rules

def test_get_full_attribute_name_simple():
    """Test _get_full_attribute_name with simple attribute chain."""
    validator = PolicyValidator([])
    node = ast.parse('module.function.call', mode='eval').body
    result = validator._get_full_attribute_name(node)
    assert result == 'module.function.call'

def test_get_full_attribute_name_nested():
    """Test _get_full_attribute_name with deeply nested attributes."""
    validator = PolicyValidator([])
    node = ast.parse('a.b.c.d.e', mode='eval').body
    result = validator._get_full_attribute_name(node)
    assert result == 'a.b.c.d.e'

def test_get_full_attribute_name_single_attribute():
    """Test _get_full_attribute_name with single attribute."""
    validator = PolicyValidator([])
    node = ast.parse('obj.method', mode='eval').body
    result = validator._get_full_attribute_name(node)
    assert result == 'obj.method'

def test_find_dangerous_patterns_forbidden_call():
    """Test detection of forbidden function calls."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['exec(', 'eval(', 'compile(']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = '\ndef test():\n    result = eval("2+2")\n    exec("print(\'hello\')")\n    safe = compile("code", "<string>", "exec")\n'
    tree = ast.parse(code)
    violations = validator._find_dangerous_patterns(tree, '/test/file.py')
    assert len(violations) == 3
    violation_messages = [v['message'] for v in violations]
    assert "Use of forbidden call: 'eval'" in violation_messages
    assert "Use of forbidden call: 'exec'" in violation_messages
    assert "Use of forbidden call: 'compile'" in violation_messages

def test_find_dangerous_patterns_excluded_file():
    """Test that excluded files don't trigger violations."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['eval(']}, 'scope': {'exclude': ['/test/*.py']}}]
    validator = PolicyValidator(safety_rules)
    code = "result = eval('2+2')"
    tree = ast.parse(code)
    violations = validator._find_dangerous_patterns(tree, '/test/file.py')
    assert violations == []

def test_find_dangerous_patterns_non_excluded_file():
    """Test that non-excluded files still trigger violations."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['eval(']}, 'scope': {'exclude': ['/other/*.py']}}]
    validator = PolicyValidator(safety_rules)
    code = "result = eval('2+2')"
    tree = ast.parse(code)
    violations = validator._find_dangerous_patterns(tree, '/test/file.py')
    assert len(violations) == 1
    assert violations[0]['message'] == "Use of forbidden call: 'eval'"

def test_find_dangerous_patterns_mixed_rules():
    """Test multiple safety rules working together."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['exec(']}, 'scope': {'exclude': []}}, {'id': 'no_unsafe_imports', 'detection': {'forbidden': ['import pickle']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = "\nimport pickle\nexec('code')\n"
    tree = ast.parse(code)
    violations = validator._find_dangerous_patterns(tree, '/test/file.py')
    assert len(violations) == 2
    violation_rules = [v['rule'] for v in violations]
    assert 'safety.dangerous_call' in violation_rules
    assert 'safety.forbidden_import' in violation_rules

def test_find_dangerous_patterns_attribute_call():
    """Test detection of forbidden calls using attribute syntax."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['os.system(']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = "os.system('ls -la')"
    tree = ast.parse(code)
    violations = validator._find_dangerous_patterns(tree, '/test/file.py')
    assert len(violations) == 1
    assert violations[0]['message'] == "Use of forbidden call: 'os.system'"

def test_find_dangerous_patterns_no_violations():
    """Test code with no violations returns empty list."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['eval(']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = '\ndef safe_function():\n    return 42\n'
    tree = ast.parse(code)
    violations = validator._find_dangerous_patterns(tree, '/test/file.py')
    assert violations == []

def test_check_semantics_valid_code():
    """Test check_semantics with valid Python code."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['eval(']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = "result = eval('2+2')"
    violations = validator.check_semantics(code, '/test/file.py')
    assert len(violations) == 1
    assert violations[0]['rule'] == 'safety.dangerous_call'

def test_check_semantics_syntax_error():
    """Test check_semantics with invalid Python code."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['eval(']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = 'def invalid python syntax'
    violations = validator.check_semantics(code, '/test/file.py')
    assert violations == []

def test_check_semantics_empty_code():
    """Test check_semantics with empty string."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['eval(']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = ''
    violations = validator.check_semantics(code, '/test/file.py')
    assert violations == []

def test_find_dangerous_patterns_line_numbers():
    """Test that violations include correct line numbers."""
    safety_rules = [{'id': 'no_dangerous_execution', 'detection': {'patterns': ['eval(']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = "line1 = 1\nline2 = 2\nresult = eval('2+2')\nline4 = 4\n"
    tree = ast.parse(code)
    violations = validator._find_dangerous_patterns(tree, '/test/file.py')
    assert len(violations) == 1
    assert violations[0]['line'] == 3

def test_find_dangerous_patterns_import_from_no_module():
    """Test ImportFrom without module attribute."""
    safety_rules = [{'id': 'no_unsafe_imports', 'detection': {'forbidden': ['import os']}, 'scope': {'exclude': []}}]
    validator = PolicyValidator(safety_rules)
    code = 'from . import something'
    tree = ast.parse(code)
    violations = validator._find_dangerous_patterns(tree, '/test/file.py')
    assert violations == []
