"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/action_types.py
- Symbol: ActionImpact
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:09:18
"""

import pytest
from shared.action_types import ActionImpact

# ActionImpact is an Enum class with string values - returns ActionImpact enum members

def test_action_impact_is_enum():
    """Test that ActionImpact is properly defined as an Enum."""
    assert isinstance(ActionImpact.READ_ONLY, ActionImpact)
    assert isinstance(ActionImpact.WRITE_METADATA, ActionImpact)
    assert isinstance(ActionImpact.WRITE_CODE, ActionImpact)
    assert isinstance(ActionImpact.WRITE_DATA, ActionImpact)

def test_action_impact_values():
    """Test that each enum member has the correct string value."""
    assert ActionImpact.READ_ONLY.value == "read-only"
    assert ActionImpact.WRITE_METADATA.value == "write-metadata"
    assert ActionImpact.WRITE_CODE.value == "write-code"
    assert ActionImpact.WRITE_DATA.value == "write-data"

def test_action_impact_names():
    """Test that enum members have the correct names."""
    assert ActionImpact.READ_ONLY.name == "READ_ONLY"
    assert ActionImpact.WRITE_METADATA.name == "WRITE_METADATA"
    assert ActionImpact.WRITE_CODE.name == "WRITE_CODE"
    assert ActionImpact.WRITE_DATA.name == "WRITE_DATA"

def test_action_impact_iteration():
    """Test that all enum members are present and in expected order."""
    members = list(ActionImpact)
    assert len(members) == 4
    assert members == [
        ActionImpact.READ_ONLY,
        ActionImpact.WRITE_METADATA,
        ActionImpact.WRITE_CODE,
        ActionImpact.WRITE_DATA,
    ]

def test_action_impact_string_representation():
    """Test string representation of enum members."""
    assert str(ActionImpact.READ_ONLY) == "ActionImpact.READ_ONLY"
    assert str(ActionImpact.WRITE_CODE) == "ActionImpact.WRITE_CODE"

def test_action_impact_comparison():
    """Test that enum members can be compared properly."""
    # Test equality
    assert ActionImpact.READ_ONLY == ActionImpact.READ_ONLY
    assert ActionImpact.WRITE_METADATA != ActionImpact.WRITE_CODE

    # Test identity
    read_only_ref = ActionImpact.READ_ONLY
    assert ActionImpact.READ_ONLY is read_only_ref

def test_action_impact_value_access():
    """Test accessing enum by value."""
    assert ActionImpact("read-only") == ActionImpact.READ_ONLY
    assert ActionImpact("write-code") == ActionImpact.WRITE_CODE
    assert ActionImpact("write-data") == ActionImpact.WRITE_DATA
    assert ActionImpact("write-metadata") == ActionImpact.WRITE_METADATA

def test_action_impact_invalid_value():
    """Test that invalid values raise ValueError."""
    with pytest.raises(ValueError):
        ActionImpact("invalid-impact")

    with pytest.raises(ValueError):
        ActionImpact("")

def test_action_impact_docstrings():
    """Test that docstrings are present (though not directly testable via value)."""
    # While we can't directly assert on docstrings in a simple way,
    # we can verify the class has the expected documentation
    assert "Classification of an action's impact on system state" in ActionImpact.__doc__

    # Verify members have docstring attributes
    assert hasattr(ActionImpact.READ_ONLY, "__doc__")
    assert hasattr(ActionImpact.WRITE_CODE, "__doc__")

def test_action_impact_member_access():
    """Test alternative ways to access enum members."""
    # Access via getattr
    assert getattr(ActionImpact, "READ_ONLY") == ActionImpact.READ_ONLY
    assert getattr(ActionImpact, "WRITE_DATA") == ActionImpact.WRITE_DATA

    # Access via dictionary-style
    assert ActionImpact["READ_ONLY"] == ActionImpact.READ_ONLY
    assert ActionImpact["WRITE_METADATA"] == ActionImpact.WRITE_METADATA

def test_action_impact_hashable():
    """Test that enum members are hashable and can be used in sets/dicts."""
    impact_set = {
        ActionImpact.READ_ONLY,
        ActionImpact.WRITE_METADATA,
        ActionImpact.WRITE_CODE,
        ActionImpact.WRITE_DATA,
    }
    assert len(impact_set) == 4

    impact_dict = {
        ActionImpact.READ_ONLY: "low risk",
        ActionImpact.WRITE_CODE: "high risk",
    }
    assert impact_dict[ActionImpact.READ_ONLY] == "low risk"
    assert impact_dict[ActionImpact.WRITE_CODE] == "high risk"
