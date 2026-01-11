"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/schemas.py
- Symbol: PolicyResource
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:58:58
"""

import pytest
from mind.governance.schemas import PolicyResource

# PolicyResource is a dataclass-like structure with typed fields, not a function.
# It has synchronous __init__ method, so tests use regular 'def' functions.

def test_policy_resource_initialization_with_minimal_fields():
    """Test basic initialization with required fields."""
    policy = PolicyResource(
        policy_id="PR-001",
        version="1.0",
        title="Data Privacy Policy",
        status="active",
        purpose="Ensure user data protection"
    )

    assert policy.policy_id == "PR-001"
    assert policy.version == "1.0"
    assert policy.title == "Data Privacy Policy"
    assert policy.status == "active"
    assert policy.purpose == "Ensure user data protection"
    assert policy.rules == []
    assert policy.metadata == {}
    assert policy.source_file == ""

def test_policy_resource_initialization_with_all_fields():
    """Test initialization with all fields including optional ones."""
    rules = [
        {"id": "R1", "description": "Encrypt all sensitive data"},
        {"id": "R2", "description": "Regular security audits"}
    ]
    metadata = {"category": "security", "author": "Governance Team"}

    policy = PolicyResource(
        policy_id="PR-002",
        version="2.1",
        title="Access Control Policy",
        status="draft",
        purpose="Manage system access permissions",
        rules=rules,
        metadata=metadata,
        source_file="/full/path/to/policy.md"
    )

    assert policy.policy_id == "PR-002"
    assert policy.version == "2.1"
    assert policy.title == "Access Control Policy"
    assert policy.status == "draft"
    assert policy.purpose == "Manage system access permissions"
    assert policy.rules == rules
    assert policy.metadata == metadata
    assert policy.source_file == "/full/path/to/policy.md"

def test_policy_resource_default_fields_are_independent():
    """Test that default list/dict fields are independent instances."""
    policy1 = PolicyResource(
        policy_id="P1",
        version="1.0",
        title="Test1",
        status="active",
        purpose="Test"
    )

    policy2 = PolicyResource(
        policy_id="P2",
        version="1.0",
        title="Test2",
        status="active",
        purpose="Test"
    )

    # Modify policy1's default fields
    policy1.rules.append({"test": "rule"})
    policy1.metadata["modified"] = True

    # policy2 should remain unaffected
    assert policy2.rules == []
    assert policy2.metadata == {}
    assert policy1.rules == [{"test": "rule"}]
    assert policy1.metadata == {"modified": True}

def test_policy_resource_with_empty_string_fields():
    """Test handling of empty string values."""
    policy = PolicyResource(
        policy_id="",
        version="",
        title="",
        status="",
        purpose="",
        source_file=""
    )

    assert policy.policy_id == ""
    assert policy.version == ""
    assert policy.title == ""
    assert policy.status == ""
    assert policy.purpose == ""
    assert policy.source_file == ""

def test_policy_resource_field_types():
    """Verify field types accept appropriate values."""
    policy = PolicyResource(
        policy_id="PR-003",
        version="3.0-beta",
        title="Title with spaces and punctuation!",
        status="archived",
        purpose="A purpose string with unicode: …",
        rules=[{"key": "value", "number": 123}],
        metadata={"nested": {"inner": "value"}, "list": [1, 2, 3]},
        source_file="C:\\Windows\\Path\\policy.md"
    )

    assert isinstance(policy.policy_id, str)
    assert isinstance(policy.version, str)
    assert isinstance(policy.title, str)
    assert isinstance(policy.status, str)
    assert isinstance(policy.purpose, str)
    assert isinstance(policy.rules, list)
    assert isinstance(policy.metadata, dict)
    assert isinstance(policy.source_file, str)

    # Verify Unicode ellipsis is preserved
    assert "…" in policy.purpose
    assert policy.purpose == "A purpose string with unicode: …"

def test_policy_resource_equality_by_value():
    """Test that two instances with same values are equal by field comparison."""
    policy1 = PolicyResource(
        policy_id="PR-001",
        version="1.0",
        title="Test Policy",
        status="active",
        purpose="Testing"
    )

    policy2 = PolicyResource(
        policy_id="PR-001",
        version="1.0",
        title="Test Policy",
        status="active",
        purpose="Testing"
    )

    # Compare field by field (not using 'is' operator)
    assert policy1.policy_id == policy2.policy_id
    assert policy1.version == policy2.version
    assert policy1.title == policy2.title
    assert policy1.status == policy2.status
    assert policy1.purpose == policy2.purpose
    assert policy1.rules == policy2.rules
    assert policy1.metadata == policy2.metadata
    assert policy1.source_file == policy2.source_file
