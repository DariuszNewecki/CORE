"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/validator_service.py
- Symbol: get_validator
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:25:46
"""

from mind.governance.validator_service import get_validator


# Detected return type: ConstitutionalValidator


def test_get_validator_returns_same_instance():
    """Test that get_validator returns the same instance on subsequent calls."""
    validator1 = get_validator()
    validator2 = get_validator()
    assert validator1 == validator2


def test_get_validator_returns_constitutional_validator():
    """Test that get_validator returns an instance of ConstitutionalValidator."""
    validator = get_validator()
    # Check type by comparing class name string to avoid direct import
    assert validator.__class__.__name__ == "ConstitutionalValidator"
