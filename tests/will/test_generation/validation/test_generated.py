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
