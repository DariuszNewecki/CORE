"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/violation_report.py
- Symbol: ConstitutionalViolationError
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:45:54
"""

import pytest

from mind.governance.violation_report import ConstitutionalViolationError


# Detected return type: ConstitutionalViolationError is a class, not a function. It is not async.


def test_constitutional_violation_error_is_exception_subclass():
    """Test that ConstitutionalViolationError is a subclass of Exception."""
    assert issubclass(ConstitutionalViolationError, Exception)


def test_constitutional_violation_error_instantiation_with_message():
    """Test that ConstitutionalViolationError can be instantiated with a message."""
    error_message = "Change violates policy 42"
    error_instance = ConstitutionalViolationError(error_message)
    assert str(error_instance) == error_message


def test_constitutional_violation_error_instantiation_without_message():
    """Test that ConstitutionalViolationError can be instantiated without a message."""
    error_instance = ConstitutionalViolationError()
    assert str(error_instance) == ""


def test_constitutional_violation_error_inherits_exception_behavior():
    """Test that ConstitutionalViolationError behaves like a standard Exception."""
    try:
        raise ConstitutionalViolationError("Test violation")
    except ConstitutionalViolationError as e:
        assert str(e) == "Test violation"
    except Exception:
        pytest.fail(
            "ConstitutionalViolationError should be caught by its own type, not a generic Exception."
        )


def test_constitutional_violation_error_docstring():
    """Test that the class has the correct docstring."""
    expected_docstring = """
    Raised when proposed changes violate constitutional policies.

    Used by IntentGuard to signal hard blocks (e.g., .intent writes).
    """
    # Compare normalized docstrings (strip leading/trailing whitespace)
    assert ConstitutionalViolationError.__doc__.strip() == expected_docstring.strip()
