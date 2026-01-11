"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/exceptions.py
- Symbol: CoreException
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:15:40
"""

from shared.exceptions import CoreException


# Detected return type: CoreException is a regular Exception subclass, not async.
# Therefore, all test functions are regular 'def'.


def test_coreexception_inherits_from_exception():
    """Test that CoreException is a subclass of Exception."""
    assert issubclass(CoreException, Exception)


def test_coreexception_initialization():
    """Test that the exception is initialized with the provided message."""
    test_message = "A test error occurred"
    exc = CoreException(test_message)
    assert exc.message == test_message
    # Also check the parent's args tuple
    assert exc.args == (test_message,)


def test_coreexception_string_representation():
    """Test that str(CoreException) returns the message."""
    test_message = "Another error"
    exc = CoreException(test_message)
    assert str(exc) == test_message


def test_coreexception_with_empty_message():
    """Test CoreException can be initialized with an empty string."""
    exc = CoreException("")
    assert exc.message == ""
    assert str(exc) == ""
    assert exc.args == ("",)


def test_coreexception_with_complex_message():
    """Test CoreException with a multi-line or formatted message."""
    complex_msg = "Error at line 42\nDetails: Invalid input"
    exc = CoreException(complex_msg)
    assert exc.message == complex_msg
    assert str(exc) == complex_msg
