"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/validator_service.py
- Symbol: ApprovalType
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:24:43
"""

import pytest

from mind.governance.validator_service import ApprovalType


# Detected return type: Enum member values (strings)


def test_approval_type_values():
    """Test that each ApprovalType enum member has the correct string value."""
    assert ApprovalType.AUTONOMOUS.value == "autonomous"
    assert ApprovalType.VALIDATION_ONLY.value == "validation_only"
    assert ApprovalType.HUMAN_CONFIRMATION.value == "human_confirmation"
    assert ApprovalType.HUMAN_REVIEW.value == "human_review"


def test_approval_type_names():
    """Test that each ApprovalType enum member has the correct name."""
    assert ApprovalType.AUTONOMOUS.name == "AUTONOMOUS"
    assert ApprovalType.VALIDATION_ONLY.name == "VALIDATION_ONLY"
    assert ApprovalType.HUMAN_CONFIRMATION.name == "HUMAN_CONFIRMATION"
    assert ApprovalType.HUMAN_REVIEW.name == "HUMAN_REVIEW"


def test_approval_type_iteration():
    """Test that all ApprovalType enum members are present and in order."""
    members = list(ApprovalType)
    assert len(members) == 4
    assert members[0] == ApprovalType.AUTONOMOUS
    assert members[1] == ApprovalType.VALIDATION_ONLY
    assert members[2] == ApprovalType.HUMAN_CONFIRMATION
    assert members[3] == ApprovalType.HUMAN_REVIEW


def test_approval_type_comparison():
    """Test that ApprovalType members can be compared correctly."""
    # Test equality
    assert ApprovalType.AUTONOMOUS == ApprovalType.AUTONOMOUS
    assert ApprovalType.HUMAN_REVIEW == ApprovalType.HUMAN_REVIEW

    # Test inequality
    assert ApprovalType.AUTONOMOUS != ApprovalType.HUMAN_CONFIRMATION
    assert ApprovalType.VALIDATION_ONLY != ApprovalType.HUMAN_REVIEW


def test_approval_type_string_representation():
    """Test the string representation of ApprovalType members."""
    assert str(ApprovalType.AUTONOMOUS) == "ApprovalType.AUTONOMOUS"
    assert str(ApprovalType.HUMAN_CONFIRMATION) == "ApprovalType.HUMAN_CONFIRMATION"


def test_approval_type_value_access():
    """Test accessing ApprovalType values through the value property."""
    autonomous = ApprovalType.AUTONOMOUS
    assert autonomous.value == "autonomous"

    human_review = ApprovalType.HUMAN_REVIEW
    assert human_review.value == "human_review"


def test_approval_type_membership():
    """Test that ApprovalType members are properly registered in the enum."""
    assert "AUTONOMOUS" in ApprovalType.__members__
    assert "VALIDATION_ONLY" in ApprovalType.__members__
    assert "HUMAN_CONFIRMATION" in ApprovalType.__members__
    assert "HUMAN_REVIEW" in ApprovalType.__members__
    assert "INVALID_NAME" not in ApprovalType.__members__


def test_approval_type_value_lookup():
    """Test looking up ApprovalType members by value."""
    assert ApprovalType("autonomous") == ApprovalType.AUTONOMOUS
    assert ApprovalType("validation_only") == ApprovalType.VALIDATION_ONLY
    assert ApprovalType("human_confirmation") == ApprovalType.HUMAN_CONFIRMATION
    assert ApprovalType("human_review") == ApprovalType.HUMAN_REVIEW


def test_approval_type_invalid_value_lookup():
    """Test that looking up invalid values raises ValueError."""
    with pytest.raises(ValueError):
        ApprovalType("invalid_value")

    with pytest.raises(ValueError):
        ApprovalType("")

    with pytest.raises(ValueError):
        ApprovalType(None)


def test_approval_type_docstring():
    """Test that the ApprovalType class has the correct docstring."""
    assert ApprovalType.__doc__ == "Approval mechanism required."
