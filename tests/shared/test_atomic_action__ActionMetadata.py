"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/atomic_action.py
- Symbol: ActionMetadata
- Status: 1 tests passed, some failed
- Passing tests: test_action_metadata_initialization_with_all_fields
- Generated: 2026-01-11 01:01:53
"""

import pytest
from shared.atomic_action import ActionMetadata, ActionImpact

def test_action_metadata_initialization_with_all_fields():
    """Test that ActionMetadata can be initialized with all fields."""
    metadata = ActionMetadata(action_id='fix.ids', intent='Fix identifier naming issues', impact=ActionImpact.READ_ONLY, policies=['naming.convention', 'safety.immutable'], category='fixers')
    assert metadata.action_id == 'fix.ids'
    assert metadata.intent == 'Fix identifier naming issues'
    assert metadata.impact == ActionImpact.READ_ONLY
    assert metadata.policies == ['naming.convention', 'safety.immutable']
    assert metadata.category == 'fixers'
