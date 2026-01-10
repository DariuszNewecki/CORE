"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/atomic_action.py
- Symbol: ActionMetadata
- Status: 2 tests passed, some failed
- Passing tests: test_actionmetadata_initialization_without_optional_category, test_actionmetadata_policies_empty_list
- Generated: 2026-01-11 00:16:27
"""

import pytest
from shared.atomic_action import ActionMetadata, ActionImpact

def test_actionmetadata_initialization_without_optional_category():
    """Test initialization without the optional category field."""
    metadata = ActionMetadata(action_id='check.imports', intent='Verify import statements are correct', impact=ActionImpact.READ_ONLY, policies=['security.imports', 'correctness.basic'])
    assert metadata.action_id == 'check.imports'
    assert metadata.intent == 'Verify import statements are correct'
    assert metadata.impact == ActionImpact.READ_ONLY
    assert metadata.policies == ['security.imports', 'correctness.basic']
    assert metadata.category is None

def test_actionmetadata_policies_empty_list():
    """Test that policies can be an empty list."""
    metadata = ActionMetadata(action_id='no.policy.action', intent='Action with no governing policies', impact=ActionImpact.READ_ONLY, policies=[], category='unregulated')
    assert metadata.policies == []
