"""validate_yaml_code reports every YAMLError as a violation (#1386).

Only MarkedYAMLError has ``problem_mark``. A ReaderError (a control
character in the input) is a plain YAMLError: reading ``problem_mark`` on it
raised AttributeError out of the except, crashing the validation pipeline.
"""

from __future__ import annotations

from shared.infrastructure.validation.yaml_validator import validate_yaml_code


# ID: 0a9d3b1e-5f7c-4e2a-8b6d-1c3e5f7a9b20
def test_reader_error_is_a_violation_without_line():
    code = "key: \x07\n"

    returned, violations = validate_yaml_code(code)

    assert returned == code
    assert len(violations) == 1
    assert violations[0]["rule"] == "syntax.yaml"
    assert violations[0]["line"] == 0


# ID: 6e2b8c4d-3a1f-4b9e-9c7d-5f0a2e4b6d81
def test_marked_error_reports_its_line():
    _, violations = validate_yaml_code("a: 1\nb: [unclosed\n")

    assert len(violations) == 1
    assert violations[0]["line"] >= 2


# ID: 9f4c6a2e-8b1d-4d3f-a5e7-2b9c1d3f5a64
def test_valid_yaml_has_no_violations():
    assert validate_yaml_code("a: 1\n") == ("a: 1\n", [])
