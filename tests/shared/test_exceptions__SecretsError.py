"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/exceptions.py
- Symbol: SecretsError
- Status: 4 tests passed, some failed
- Passing tests: test_secretserror_instantiation_with_message, test_secretserror_instantiation_with_empty_message, test_secretserror_instantiation_with_complex_message, test_secretserror_is_exception
- Generated: 2026-01-11 01:15:51
"""

from shared.exceptions import SecretsError


def test_secretserror_instantiation_with_message():
    """Test basic instantiation with a message."""
    message = "Secret not found"
    exc = SecretsError(message)
    assert str(exc) == message


def test_secretserror_instantiation_with_empty_message():
    """Test instantiation with an empty message."""
    exc = SecretsError("")
    assert str(exc) == ""


def test_secretserror_instantiation_with_complex_message():
    """Test instantiation with a message containing special characters."""
    message = "Secret 'db_password' contains invalid character: @"
    exc = SecretsError(message)
    assert str(exc) == message


def test_secretserror_is_exception():
    """Test that SecretsError is a subclass of Exception."""
    exc = SecretsError("test")
    assert isinstance(exc, Exception)
