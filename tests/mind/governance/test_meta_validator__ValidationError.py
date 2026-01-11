"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/meta_validator.py
- Symbol: ValidationError
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:08:34
"""

import pytest
from mind.governance.meta_validator import ValidationError


# ValidationError is a class (dataclass or pydantic model). Tests will instantiate it and check attributes.

def test_validationerror_initialization_with_minimal_fields():
    """Test that ValidationError can be created with required fields."""
    error = ValidationError(
        document="doc1",
        error_type="type_mismatch",
        message="The value is incorrect."
    )
    assert error.document == "doc1"
    assert error.error_type == "type_mismatch"
    assert error.message == "The value is incorrect."
    assert error.severity == "error"
    assert error.field is None


def test_validationerror_initialization_with_all_fields():
    """Test that ValidationError can be created with all fields, including optional ones."""
    error = ValidationError(
        document="report.pdf",
        error_type="missing_field",
        message="Required field 'author' is missing.",
        severity="warning",
        field="author"
    )
    assert error.document == "report.pdf"
    assert error.error_type == "missing_field"
    assert error.message == "Required field 'author' is missing."
    assert error.severity == "warning"
    assert error.field == "author"


def test_validationerror_default_severity():
    """Test that the default severity is 'error'."""
    error = ValidationError(
        document="d",
        error_type="t",
        message="m"
    )
    assert error.severity == "error"


def test_validationerror_default_field_is_none():
    """Test that the default field is None."""
    error = ValidationError(
        document="d",
        error_type="t",
        message="m"
    )
    assert error.field is None


def test_validationerror_attribute_assignment():
    """Test that attributes are accessible and match the provided values."""
    test_doc = "/full/path/to/document.txt"
    test_msg = "Invalid format detected"
    err = ValidationError(
        document=test_doc,
        error_type="format_error",
        message=test_msg,
        field="header"
    )
    assert err.document == test_doc
    assert err.message == test_msg
    assert err.field == "header"
