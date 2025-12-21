# tests/services/validation/test_yaml_validator.py
"""Tests for yaml_validator module."""

from __future__ import annotations

from services.validation.yaml_validator import validate_yaml_code


class TestValidateYamlCode:
    """Tests for validate_yaml_code function."""

    def test_valid_yaml(self):
        """Test that valid YAML passes validation."""
        code = "key: value\nlist:\n  - item1\n  - item2"
        result_code, violations = validate_yaml_code(code)
        assert result_code == code
        assert violations == []

    def test_invalid_yaml_syntax(self):
        """Test that invalid YAML syntax is detected."""
        code = "key: value\n  invalid: indentation:"
        _result_code, violations = validate_yaml_code(code)
        assert len(violations) == 1
        assert violations[0]["rule"] == "syntax.yaml"
        assert violations[0]["severity"] == "error"

    def test_empty_yaml(self):
        """Test that empty YAML is valid."""
        code = ""
        _result_code, violations = validate_yaml_code(code)
        assert violations == []

    def test_yaml_with_special_chars(self):
        """Test YAML with special characters."""
        code = "message: 'Hello: World!'\npath: /usr/bin"
        _result_code, violations = validate_yaml_code(code)
        assert violations == []

    def test_malformed_yaml(self):
        """Test completely malformed YAML."""
        code = "{{{"
        _result_code, violations = validate_yaml_code(code)
        assert len(violations) >= 1
        assert violations[0]["severity"] == "error"
