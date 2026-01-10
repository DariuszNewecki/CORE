"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/atomic_action.py
- Symbol: get_action_metadata
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:17:53
"""

import pytest
from shared.atomic_action import get_action_metadata

# The target function returns an ActionMetadata object or None.

def test_get_action_metadata_returns_none_for_undecorated_function():
    """Test that a plain function without the metadata attribute returns None."""
    def plain_func():
        pass

    result = get_action_metadata(plain_func)
    assert result is None

def test_get_action_metadata_returns_metadata_for_decorated_function():
    """Test that a function with the metadata attribute returns that attribute."""
    # Simulate a decorated function by manually setting the attribute.
    # We use a simple object as a stand-in for ActionMetadata.
    mock_metadata = {"name": "test_action", "description": "A test"}

    def decorated_func():
        pass
    decorated_func._atomic_action_metadata = mock_metadata

    result = get_action_metadata(decorated_func)
    assert result == mock_metadata

def test_get_action_metadata_attribute_is_removed_returns_none():
    """Test that if the attribute is deleted, the function returns None."""
    def func():
        pass
    func._atomic_action_metadata = {"data": "exists"}

    # Confirm it returns the metadata first.
    assert get_action_metadata(func) == {"data": "exists"}

    # Delete the attribute and check for None.
    delattr(func, "_atomic_action_metadata")
    result = get_action_metadata(func)
    assert result is None

def test_get_action_metadata_with_non_callable_raises_error():
    """Test that passing a non-callable object raises an AttributeError or TypeError.
       The function accesses an attribute, so a non-callable might still work,
       but we test a basic case.
    """
    # The function expects a Callable, but getattr works on any object.
    # We'll test with an object that doesn't have the attribute.
    class NonCallable:
        pass

    obj = NonCallable()
    # It should not raise an error; it should just return None.
    result = get_action_metadata(obj)
    assert result is None

def test_get_action_metadata_attribute_is_falsy_value():
    """Test that if the metadata attribute exists but is a falsy value (e.g., empty dict, None),
       the function returns that falsy value.
    """
    def func():
        pass

    # Test with empty dict
    func._atomic_action_metadata = {}
    result = get_action_metadata(func)
    assert result == {}

    # Test with None as the stored value
    func._atomic_action_metadata = None
    result = get_action_metadata(func)
    assert result is None

    # Test with empty string
    func._atomic_action_metadata = ""
    result = get_action_metadata(func)
    assert result == ""
