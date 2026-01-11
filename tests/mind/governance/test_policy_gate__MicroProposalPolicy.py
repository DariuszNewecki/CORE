"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/policy_gate.py
- Symbol: MicroProposalPolicy
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:02:23
"""

import pytest
from mind.governance.policy_gate import MicroProposalPolicy

# Detected return type: MicroProposalPolicy (class instance)

def test_from_dict_with_full_data():
    """Test creation with all fields populated."""
    data = {
        "allowed_actions": ["read:*", "write:docs/*"],
        "allowed_paths": ["src/**", "docs/*.md"],
        "required_evidence": {"deploy": ["approval", "test_results"]}
    }
    policy = MicroProposalPolicy.from_dict(data)
    assert policy.allowed_actions == ("read:*", "write:docs/*")
    assert policy.allowed_paths == ("src/**", "docs/*.md")
    assert policy.required_evidence == {"deploy": ["approval", "test_results"]}

def test_from_dict_with_empty_dict():
    """Test creation with an empty dictionary."""
    policy = MicroProposalPolicy.from_dict({})
    assert policy.allowed_actions == ()
    assert policy.allowed_paths == ()
    assert policy.required_evidence == {}

def test_from_dict_with_none_values():
    """Test that None values are treated as empty defaults."""
    data = {
        "allowed_actions": None,
        "allowed_paths": None,
        "required_evidence": None
    }
    policy = MicroProposalPolicy.from_dict(data)
    assert policy.allowed_actions == ()
    assert policy.allowed_paths == ()
    assert policy.required_evidence == {}

def test_from_dict_with_empty_lists_and_dict():
    """Test creation with explicitly empty containers."""
    data = {
        "allowed_actions": [],
        "allowed_paths": [],
        "required_evidence": {}
    }
    policy = MicroProposalPolicy.from_dict(data)
    assert policy.allowed_actions == ()
    assert policy.allowed_paths == ()
    assert policy.required_evidence == {}

def test_from_dict_with_falsy_non_none_values():
    """Test that falsy but non-None values (like empty strings) are handled."""
    data = {
        "allowed_actions": "",
        "allowed_paths": "",
        "required_evidence": ""
    }
    policy = MicroProposalPolicy.from_dict(data)
    # The 'or []' and 'or {}' logic will treat empty string as truthy, so it passes through.
    # The tuple() and dict() constructors will then process the empty string.
    assert policy.allowed_actions == tuple("")
    assert policy.allowed_paths == tuple("")
    assert policy.required_evidence == {}

def test_from_dict_with_partial_data():
    """Test creation when only some fields are provided."""
    data = {"allowed_actions": ["test:*"]}
    policy = MicroProposalPolicy.from_dict(data)
    assert policy.allowed_actions == ("test:*",)
    assert policy.allowed_paths == ()
    assert policy.required_evidence == {}

def test_from_dict_ensures_tuple_and_dict_types():
    """Verify the returned attributes are of specific immutable types."""
    data = {
        "allowed_actions": ["a", "b"],
        "allowed_paths": ["c"],
        "required_evidence": {"key": ["val"]}
    }
    policy = MicroProposalPolicy.from_dict(data)
    assert isinstance(policy.allowed_actions, tuple)
    assert isinstance(policy.allowed_paths, tuple)
    assert isinstance(policy.required_evidence, dict)
