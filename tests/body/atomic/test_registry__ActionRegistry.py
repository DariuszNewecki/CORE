"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/atomic/registry.py
- Symbol: ActionRegistry
- Status: 2 tests passed, some failed
- Passing tests: test_action_registry_initialization, test_get_nonexistent_action
- Generated: 2026-01-11 03:06:23
"""

import pytest
from body.atomic.registry import ActionRegistry, ActionDefinition, ActionCategory

def test_action_registry_initialization():
    """Test that ActionRegistry initializes with an empty actions dict."""
    registry = ActionRegistry()
    assert registry._actions == {}

def test_get_nonexistent_action():
    """Test retrieving a non-existent action returns None."""
    registry = ActionRegistry()
    retrieved = registry.get('does_not_exist')
    assert retrieved is None
