"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/atomic/registry.py
- Symbol: ActionCategory
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:05:07
"""

from body.atomic.registry import ActionCategory


# ActionCategory is a string Enum. Its members are instances of the class, comparable to strings.


def test_action_category_is_enum():
    """Verify ActionCategory is an Enum with string members."""
    assert isinstance(ActionCategory.FIX, ActionCategory)
    assert isinstance(ActionCategory.FIX, str)


def test_action_category_values():
    """Verify the specific string values of each category."""
    assert ActionCategory.FIX == "fix"
    assert ActionCategory.SYNC == "sync"
    assert ActionCategory.CHECK == "check"
    assert ActionCategory.BUILD == "build"


def test_action_category_iteration():
    """Verify iteration over the enum yields all members."""
    categories = list(ActionCategory)
    expected = [
        ActionCategory.FIX,
        ActionCategory.SYNC,
        ActionCategory.CHECK,
        ActionCategory.BUILD,
    ]
    assert categories == expected


def test_action_category_comparison_to_string():
    """Verify direct comparison to literal strings works."""
    assert ActionCategory.FIX == "fix"
    assert ActionCategory.SYNC == "sync"
    assert ActionCategory.CHECK == "check"
    assert ActionCategory.BUILD == "build"
    # Ensure reverse comparison also works
    assert "fix" == ActionCategory.FIX


def test_action_category_name_access():
    """Verify the .name and .value properties."""
    assert ActionCategory.FIX.name == "FIX"
    assert ActionCategory.FIX.value == "fix"
    assert ActionCategory.SYNC.name == "SYNC"
    assert ActionCategory.SYNC.value == "sync"
