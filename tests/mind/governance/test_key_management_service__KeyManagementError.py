"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/key_management_service.py
- Symbol: KeyManagementError
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:38:42
"""

from mind.governance.key_management_service import KeyManagementError


# Detected return type: The class KeyManagementError is a subclass of RuntimeError.
# It is not async (does not start with 'async def __init__').


def test_key_management_error_inheritance():
    """Test that KeyManagementError is a subclass of RuntimeError."""
    error = KeyManagementError("Test error")
    assert isinstance(error, RuntimeError)


def test_key_management_error_message():
    """Test that the error message is correctly stored."""
    test_message = "Encryption key not found"
    error = KeyManagementError(test_message)
    # Use '==' for string comparison
    assert str(error) == test_message
    assert error.args[0] == test_message


def test_key_management_error_default_exit_code():
    """Test that the default exit_code is 1."""
    error = KeyManagementError("Error")
    # Explicitly set all parameters to avoid side effects from defaults
    assert error.exit_code == 1


def test_key_management_error_custom_exit_code():
    """Test that a custom exit_code is correctly stored."""
    error = KeyManagementError("Custom error", exit_code=42)
    assert error.exit_code == 42


def test_key_management_error_with_empty_message():
    """Test initialization with an empty message string."""
    error = KeyManagementError("", exit_code=99)
    assert str(error) == ""
    assert error.exit_code == 99


def test_key_management_error_with_special_characters():
    """Test that messages with special characters are handled correctly."""
    message = "Key error: Ellipsis character … (U+2026) present"
    error = KeyManagementError(message)
    assert str(error) == message
