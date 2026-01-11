"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/atomic_action.py
- Symbol: get_action_metadata
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:02:50
"""

from shared.atomic_action import get_action_metadata


# The function returns ActionMetadata | None, so tests must handle both cases


def test_get_action_metadata_without_decorator():
    """Test that a plain function without the decorator returns None."""

    def plain_function():
        pass

    result = get_action_metadata(plain_function)
    assert result is None


def test_get_action_metadata_with_decorator():
    """Test that a decorated function returns the expected metadata."""

    # Create a mock decorated function with metadata
    class MockActionMetadata:
        def __init__(self):
            self.name = "test_action"
            self.description = "A test action"

    def decorated_function():
        pass

    metadata = MockActionMetadata()
    decorated_function._atomic_action_metadata = metadata

    result = get_action_metadata(decorated_function)
    assert result == metadata


def test_get_action_metadata_preserves_metadata_identity():
    """Test that the returned metadata is the exact same object."""

    class MockActionMetadata:
        def __init__(self):
            self.value = 42

    def test_func():
        pass

    original_metadata = MockActionMetadata()
    test_func._atomic_action_metadata = original_metadata

    retrieved_metadata = get_action_metadata(test_func)
    # For object identity comparison, 'is' is appropriate here
    # since we're testing it's the same object, not just equal
    assert retrieved_metadata is original_metadata


def test_get_action_metadata_with_none_metadata():
    """Test edge case where _atomic_action_metadata is explicitly set to None."""

    def func_with_none_metadata():
        pass

    func_with_none_metadata._atomic_action_metadata = None

    result = get_action_metadata(func_with_none_metadata)
    assert result is None


def test_get_action_metadata_with_different_callable_types():
    """Test that function works with different types of callables."""

    class CallableClass:
        def __call__(self):
            pass

    # Test with lambda
    def lambda_func(x):
        return x * 2

    result = get_action_metadata(lambda_func)
    assert result is None

    # Test with class instance
    instance = CallableClass()
    result = get_action_metadata(instance)
    assert result is None

    # Test with bound method
    class TestClass:
        def method(self):
            pass

    obj = TestClass()
    bound_method = obj.method
    result = get_action_metadata(bound_method)
    assert result is None
