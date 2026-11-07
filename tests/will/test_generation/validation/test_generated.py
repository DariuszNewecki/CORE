from __future__ import annotations

from will.test_generation.validation import GeneratedTestValidator


# ID: 794a4c80-4b80-456b-b47f-7f6f52cc813d
def test_GeneratedTestValidator():
    validator = GeneratedTestValidator()

    code = (
        "from __future__ import annotations\n"
        "import pytest\n"
        "from body.cli.pattern_checker import PatternChecker\n"
        "\n"
        "def test_something():\n"
        "    assert PatternChecker is not None\n"
    )

    result = validator.validate(code)

    assert result.ok is True
    assert result.error == ""


# ID: f8197185-e7ea-4591-80f1-5ca118086e23
def test_ValidationResult():
    from will.test_generation.validation import ValidationResult

    result = ValidationResult(ok=True)
    assert result.ok is True
    assert result.error == ""

    failed = ValidationResult(ok=False, error="boom")
    assert failed.ok is False
    assert failed.error == "boom"


# ID: 3fd0f44b-dfc5-4cf2-a70b-205ea8e71534
def test_GeneratedTestValidator_validate():
    from will.test_generation.validation import GeneratedTestValidator

    validator = GeneratedTestValidator()
    valid_code = "import pytest\n\ndef test_something():\n    assert True\n"

    result = validator.validate(valid_code)

    assert result.ok is True
    assert result.error == ""


from will.test_generation.validation import ValidationResult


# ID: d1808eac-e42f-4792-a043-4d623943b7ba
def test_validation_result_happy_path():
    result = ValidationResult(ok=True)
    assert result.ok is True
    assert result.error == ""

    failed = ValidationResult(ok=False, error="boom")
    assert failed.ok is False
    assert failed.error == "boom"
