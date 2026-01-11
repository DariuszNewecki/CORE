"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/validator_service.py
- Symbol: RiskTier
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:24:14
"""

import pytest
from mind.governance.validator_service import RiskTier

# Detected return type: RiskTier enum members (int values wrapped in Enum class)

def test_risk_tier_values():
    """Test that RiskTier enum members have correct integer values."""
    assert RiskTier.ROUTINE.value == 1
    assert RiskTier.STANDARD.value == 3
    assert RiskTier.ELEVATED.value == 7
    assert RiskTier.CRITICAL.value == 10

def test_risk_tier_names():
    """Test that RiskTier enum members have correct names."""
    assert RiskTier.ROUTINE.name == "ROUTINE"
    assert RiskTier.STANDARD.name == "STANDARD"
    assert RiskTier.ELEVATED.name == "ELEVATED"
    assert RiskTier.CRITICAL.name == "CRITICAL"

def test_risk_tier_ordering():
    """Test that RiskTier values are in increasing order of risk."""
    assert RiskTier.ROUTINE.value < RiskTier.STANDARD.value
    assert RiskTier.STANDARD.value < RiskTier.ELEVATED.value
    assert RiskTier.ELEVATED.value < RiskTier.CRITICAL.value

def test_risk_tier_iteration():
    """Test that RiskTier can be iterated over and contains all members."""
    members = list(RiskTier)
    assert len(members) == 4
    assert RiskTier.ROUTINE in members
    assert RiskTier.STANDARD in members
    assert RiskTier.ELEVATED in members
    assert RiskTier.CRITICAL in members

def test_risk_tier_lookup_by_value():
    """Test that RiskTier can be looked up by integer value."""
    assert RiskTier(1) == RiskTier.ROUTINE
    assert RiskTier(3) == RiskTier.STANDARD
    assert RiskTier(7) == RiskTier.ELEVATED
    assert RiskTier(10) == RiskTier.CRITICAL

def test_risk_tier_lookup_by_name():
    """Test that RiskTier can be looked up by name string."""
    assert RiskTier["ROUTINE"] == RiskTier.ROUTINE
    assert RiskTier["STANDARD"] == RiskTier.STANDARD
    assert RiskTier["ELEVATED"] == RiskTier.ELEVATED
    assert RiskTier["CRITICAL"] == RiskTier.CRITICAL

def test_risk_tier_invalid_value():
    """Test that looking up invalid integer value raises ValueError."""
    with pytest.raises(ValueError):
        RiskTier(0)
    with pytest.raises(ValueError):
        RiskTier(5)
    with pytest.raises(ValueError):
        RiskTier(15)

def test_risk_tier_invalid_name():
    """Test that looking up invalid name raises KeyError."""
    with pytest.raises(KeyError):
        RiskTier["INVALID"]
    with pytest.raises(KeyError):
        RiskTier["routine"]  # case-sensitive

def test_risk_tier_string_representation():
    """Test string representations of RiskTier enum members."""
    assert str(RiskTier.ROUTINE) == "RiskTier.ROUTINE"
    assert repr(RiskTier.ROUTINE) == "<RiskTier.ROUTINE: 1>"

def test_risk_tier_comparison():
    """Test that RiskTier members can be compared."""
    # Equality comparisons
    assert RiskTier.ROUTINE == RiskTier.ROUTINE
    assert RiskTier.ROUTINE != RiskTier.STANDARD

    # Identity comparisons (for completeness, though 'is' is generally avoided for values)
    assert RiskTier.ROUTINE is RiskTier.ROUTINE
    assert RiskTier.ROUTINE is not RiskTier.STANDARD

def test_risk_tier_docstring():
    """Test that RiskTier class has correct docstring."""
    assert RiskTier.__doc__ == "Risk classification for operations."
