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


# ID: d8d0ba96-45b7-423a-b42a-27becae09793
def test_PatternValidators_check_no_placeholder_test_body() -> None:
    source = "def test_something():\n    value = 1 + 1\n"
    tree = ast.parse(source)

    with patch.object(
        PatternValidators,
        "_load_test_quality_rule_statements",
        return_value={},
    ):
        violations = PatternValidators.check_no_placeholder_test_body(
            tree, "tests/test_sample.py"
        )

    assert isinstance(violations, list)
    assert len(violations) == 1
    violation = violations[0]
    assert violation.rule_name == "code.tests.no_placeholder_test_body"
    assert violation.path == "tests/test_sample.py"
    assert "test_something" in violation.message
    assert violation.severity == "error"


# ID: 29c12000-ecc2-4e9e-b2d9-b004266c334c
def test_PatternValidators_check_no_imported_symbol_redeclared():
    from body.governance.intent_pattern_validators import (
        _TEST_NO_IMPORTED_SYMBOL_REDECLARED_RULE_ID,
        PatternValidators,
    )

    source = (
        "from body.foo import Widget\n"
        "\n"
        "class Widget:\n"
        "    pass\n"
        "\n"
        "def some_other():\n"
        "    pass\n"
    )
    tree = ast.parse(source)

    with patch.object(
        PatternValidators,
        "_load_test_quality_rule_statements",
        return_value={},
    ):
        violations = PatternValidators.check_no_imported_symbol_redeclared(
            tree, "tests/test_widget.py"
        )

    assert len(violations) == 1
    violation = violations[0]
    assert violation.rule_name == _TEST_NO_IMPORTED_SYMBOL_REDECLARED_RULE_ID
    assert violation.path == "tests/test_widget.py"
    assert "Widget" in violation.message
    assert violation.severity == "error"


# ID: d0bdb7c7-dd41-42b1-9e9f-f3822a736c2c
def test_PatternValidators_check_no_magicmock_on_await() -> None:
    code = (
        "async def test_x():\n"
        "    svc = MagicMock()\n"
        "    svc.run = MagicMock()\n"
        "    await svc.run()\n"
    )
    tree = ast.parse(code)

    with patch.object(
        PatternValidators,
        "_load_test_quality_rule_statements",
        return_value={},
    ):
        violations = PatternValidators.check_no_magicmock_on_await(
            tree, code, "tests/test_x.py"
        )

    assert isinstance(violations, list)
    assert len(violations) == 1
    violation = violations[0]
    assert violation.rule_name == "code.tests.no_magicmock_on_await"
    assert violation.path == "tests/test_x.py"
    assert violation.severity == "error"
    assert "run" in violation.message


# ID: 0bfc5271-0c96-4ff9-9fe1-c37171519009
def test_PatternValidators_validate_test_file_pattern() -> None:
    cls = MagicMock()
    cls._module_resolves = MagicMock(return_value=True)
    cls._load_generated_import_rule_statements = MagicMock(return_value={})
    cls.check_no_magicmock_on_await = MagicMock(return_value=[])
    cls.check_no_imported_symbol_redeclared = MagicMock(return_value=[])
    cls.check_no_placeholder_test_body = MagicMock(return_value=[])
    cls.check_no_global_module_mutation = MagicMock(return_value=[])
    cls.check_no_unresolved_free_names = MagicMock(return_value=[])

    code = "import os\nfrom sys import path\n"

    result = PatternValidators.validate_test_file_pattern.__func__(
        cls, code, "target/test_file.py"
    )

    assert result == []
    cls._module_resolves.assert_any_call("os")
    cls._module_resolves.assert_any_call("sys")


# ID: 3af3c4fa-5786-40ca-b9f8-0cece89953f9
def test_PatternValidators():
    # Happy path: a clean test-file pattern with only valid absolute imports.
    code = "import os\n\n\ndef test_thing():\n    assert os.path.sep\n"

    with (
        patch.object(
            PatternValidators,
            "_load_generated_import_rule_statements",
            return_value={},
        ) as mock_rule_statements,
        patch.object(
            PatternValidators,
            "_load_test_quality_rule_statements",
            return_value={},
        ) as mock_tier2_statements,
    ):
        violations = PatternValidators.validate(
            code=code,
            pattern_id="test_file",
            component_type="test",
            target_path="tests/test_generated.py",
        )

    assert violations == []
    mock_rule_statements.assert_called()
    mock_tier2_statements.assert_called()
