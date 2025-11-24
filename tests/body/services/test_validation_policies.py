# tests/body/services/test_validation_policies.py
from __future__ import annotations

from body.services.validation_policies import PolicyValidator


def _make_validator() -> PolicyValidator:
    """Helper to create a PolicyValidator with simple safety rules."""
    safety_policy_rules = [
        {
            "id": "no_dangerous_execution",
            "scope": {
                "exclude": [],  # no exclusions by default
            },
            "detection": {
                # Note: validation_policies strips '(' from patterns
                "patterns": ["eval(", "os.system("],
            },
        },
        {
            "id": "no_unsafe_imports",
            "scope": {
                "exclude": [],
            },
            "detection": {
                # The implementation takes the last token, so these become
                # forbidden_imports = {"os", "subprocess"}
                "forbidden": [
                    "import os",
                    "import subprocess",
                ],
            },
        },
    ]
    return PolicyValidator(safety_policy_rules=safety_policy_rules)


def test_dangerous_call_detection() -> None:
    """PolicyValidator flags forbidden calls like eval() and os.system()."""
    validator = _make_validator()
    code = """
def run(user_code):
    eval(user_code)
    print("safe line")
"""
    file_path = "src/body/some_module.py"

    violations = validator.check_semantics(code, file_path)

    # We expect at least one dangerous_call violation for eval
    assert any(v["rule"] == "safety.dangerous_call" for v in violations)
    messages = {v["message"] for v in violations}
    assert "Use of forbidden call: 'eval'" in messages


def test_forbidden_import_detection() -> None:
    """PolicyValidator flags forbidden imports like 'import os' and 'import subprocess'."""
    validator = _make_validator()
    code = """
import os
import math
from subprocess import Popen

def foo():
    return 42
"""
    file_path = "src/body/another_module.py"

    violations = validator.check_semantics(code, file_path)

    # We expect forbidden_import violations for both os and subprocess
    rules = [v["rule"] for v in violations]
    assert "safety.forbidden_import" in rules

    messages = {v["message"] for v in violations}
    assert "Import of forbidden module: 'os'" in messages
    assert "Import from forbidden module: 'subprocess'" in messages


def test_exclude_scope_skips_violations() -> None:
    """Files matching an exclude scope pattern should not report violations."""
    # Use an exact path in the exclude pattern so Path(file_path).match()
    # is guaranteed to evaluate to True.
    excluded_path = "tests/body/some_test_file.py"

    safety_policy_rules = [
        {
            "id": "no_dangerous_execution",
            "scope": {
                "exclude": [excluded_path],
            },
            "detection": {
                "patterns": ["eval("],
            },
        }
    ]
    validator = PolicyValidator(safety_policy_rules=safety_policy_rules)

    code = """
        def run(user_code):
        eval(user_code)
    """
    file_path = excluded_path

    violations = validator.check_semantics(code, file_path)

    # Because of the exclude pattern, we expect no violations even though eval is present
    assert violations == []


def test_syntax_error_returns_empty_list() -> None:
    """Invalid Python code should result in no semantic violations (parser fails)."""
    validator = _make_validator()
    # This is intentionally invalid Python
    broken_code = "def broken(:\n    pass"
    file_path = "src/body/broken.py"

    violations = validator.check_semantics(broken_code, file_path)

    assert violations == []
