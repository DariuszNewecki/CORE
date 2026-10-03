from __future__ import annotations

from unittest.mock import MagicMock, patch

from body.governance.intent_pattern_validators import PatternValidators


# ID: 53a994f0-34b1-452c-9db8-92ba6138c5cd
def test_PatternValidators_validate() -> None:
    sentinel_violations = [MagicMock(name="violation")]

    with patch.object(
        PatternValidators,
        "validate_test_file_pattern",
        return_value=sentinel_violations,
    ) as mock_validator:
        result = PatternValidators.validate(
            "some code",
            "test_file",
            "some_component",
            "path/to/target",
        )

    mock_validator.assert_called_once_with("some code", "path/to/target")
    assert result is sentinel_violations


import ast


# ID: 9d0f4ed8-765e-427e-96e3-2dcb11b98de0
def test_PatternValidators_check_no_unresolved_free_names():
    cls = PatternValidators
    code = "import os\n\n\ndef f():\n    return os.getcwd()\n"
    tree = ast.parse(code)

    with patch.object(
        cls,
        "_load_test_quality_rule_statements",
        return_value={},
    ):
        result = cls.check_no_unresolved_free_names(tree, "test_module.py", code=code)

    assert isinstance(result, list)
    assert result == []





# ID: 467216ca-f582-4a6b-8a5c-bfaf98d28660
def test_PatternValidators_check_no_global_module_mutation() -> None:
    source = "import yaml\nyaml.safe_load = MagicMock()\n"
    tree = ast.parse(source)

    instance = PatternValidators.__new__(PatternValidators)
    instance._load_test_quality_rule_statements = MagicMock(
        return_value={
            "code.tests.no_global_module_mutation": "no global mutation",
        }
    )

    result = instance.check_no_global_module_mutation(tree, "tests/test_sample.py")

    assert isinstance(result, list)
    assert len(result) == 1
    violation = result[0]
    assert violation.rule_name == "code.tests.no_global_module_mutation"
    assert violation.path == "tests/test_sample.py"
    assert violation.severity == "error"
    assert "yaml.safe_load" in violation.message
    assert "monkeypatch.setattr" in violation.suggested_fix
