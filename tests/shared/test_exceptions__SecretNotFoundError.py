"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/exceptions.py
- Symbol: SecretNotFoundError
- Status: 4 tests passed, some failed
- Passing tests: test_secretnotfounderror_message, test_secretnotfounderror_key_attribute, test_secretnotfounderror_with_empty_key, test_secretnotfounderror_with_special_characters_key
- Generated: 2026-01-11 01:16:02
"""

import pytest
from shared.exceptions import SecretNotFoundError

def test_secretnotfounderror_message():
    """Test the error message is formatted correctly."""
    key = 'MY_API_KEY'
    error = SecretNotFoundError(key)
    expected_message = f'Secret not found: {key}'
    assert error.args[0] == expected_message
    assert str(error) == expected_message

def test_secretnotfounderror_key_attribute():
    """Test that the key is stored as an instance attribute."""
    key = 'DATABASE_PASSWORD'
    error = SecretNotFoundError(key)
    assert error.key == key

def test_secretnotfounderror_with_empty_key():
    """Test initialization with an empty key string."""
    key = ''
    error = SecretNotFoundError(key)
    assert error.key == key
    assert str(error) == 'Secret not found: '

def test_secretnotfounderror_with_special_characters_key():
    """Test initialization with a key containing special characters."""
    key = 'key/with/slashes-and.dots'
    error = SecretNotFoundError(key)
    assert error.key == key
    assert str(error) == f'Secret not found: {key}'
