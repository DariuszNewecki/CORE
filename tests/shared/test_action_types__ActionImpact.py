"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/action_types.py
- Symbol: ActionImpact
- Status: 5 tests passed, some failed
- Passing tests: test_action_impact_members_exist, test_action_impact_values, test_action_impact_iteration, test_action_impact_access_by_name, test_action_impact_access_by_value
- Generated: 2026-01-11 00:53:23
"""

import pytest
from shared.action_types import ActionImpact

def test_action_impact_members_exist():
    """Verify all expected members are defined."""
    expected_members = {'READ_ONLY', 'WRITE_METADATA', 'WRITE_CODE', 'WRITE_DATA'}
    actual_members = {member.name for member in ActionImpact}
    assert actual_members == expected_members

def test_action_impact_values():
    """Verify the string value associated with each member."""
    assert ActionImpact.READ_ONLY.value == 'read-only'
    assert ActionImpact.WRITE_METADATA.value == 'write-metadata'
    assert ActionImpact.WRITE_CODE.value == 'write-code'
    assert ActionImpact.WRITE_DATA.value == 'write-data'

def test_action_impact_iteration():
    """Verify iteration order and completeness."""
    members_in_order = list(ActionImpact)
    assert members_in_order == [ActionImpact.READ_ONLY, ActionImpact.WRITE_METADATA, ActionImpact.WRITE_CODE, ActionImpact.WRITE_DATA]

def test_action_impact_access_by_name():
    """Verify members can be accessed by name."""
    assert ActionImpact['READ_ONLY'] is ActionImpact.READ_ONLY
    assert ActionImpact['WRITE_METADATA'] is ActionImpact.WRITE_METADATA
    assert ActionImpact['WRITE_CODE'] is ActionImpact.WRITE_CODE
    assert ActionImpact['WRITE_DATA'] is ActionImpact.WRITE_DATA

def test_action_impact_access_by_value():
    """Verify members can be accessed by their value."""
    assert ActionImpact('read-only') is ActionImpact.READ_ONLY
    assert ActionImpact('write-metadata') is ActionImpact.WRITE_METADATA
    assert ActionImpact('write-code') is ActionImpact.WRITE_CODE
    assert ActionImpact('write-data') is ActionImpact.WRITE_DATA
