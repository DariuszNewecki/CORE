"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/ast_gate/checks/knowledge_source_check.py
- Symbol: KnowledgeSourceCheck
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:35:12
"""

import pytest

from mind.logic.engines.ast_gate.checks.knowledge_source_check import (
    KnowledgeSourceCheck,
)


# The verify method returns List[AuditFinding] - an async method that returns audit findings


@pytest.mark.asyncio
async def test_knowledge_source_check_initialization():
    """Test that KnowledgeSourceCheck initializes with correct policy rules and enforcement methods."""
    check = KnowledgeSourceCheck()

    # Check policy rule IDs
    assert check.policy_rule_ids == [
        "db.ssot_for_operational_data",
        "db.cli_registry_in_db",
        "db.llm_resources_in_db",
        "db.cognitive_roles_in_db",
        "db.domains_in_db",
    ]

    # Check enforcement methods count matches policy rules count
    assert len(check.enforcement_methods) == 5

    # Check that it's a concrete check
    assert check._is_concrete_check


@pytest.mark.asyncio
async def test_knowledge_source_check_verify_with_empty_context():
    """Test verify method with empty context and rule_data."""
    check = KnowledgeSourceCheck()

    # Test with empty context and rule_data
    context = {}
    rule_data = {}

    findings = await check.verify(context, rule_data)

    # Should return a list (even if empty)
    assert isinstance(findings, list)

    # The actual content depends on the enforcement methods' behavior
    # but we verify the structure is correct


@pytest.mark.asyncio
async def test_knowledge_source_check_verify_with_context_data():
    """Test verify method with populated context and rule_data."""
    check = KnowledgeSourceCheck()

    # Test with some data in context and rule_data
    context = {"database": "test_db", "environment": "test"}
    rule_data = {"rule_id": "test_rule", "severity": "high"}

    findings = await check.verify(context, rule_data)

    # Should return a list
    assert isinstance(findings, list)

    # Verify method signature is respected
    # (no assertion about content since it depends on external enforcement methods)


@pytest.mark.asyncio
async def test_knowledge_source_check_verify_multiple_calls():
    """Test that verify can be called multiple times independently."""
    check = KnowledgeSourceCheck()

    context1 = {"call": "first"}
    rule_data1 = {"test": "data1"}

    context2 = {"call": "second"}
    rule_data2 = {"test": "data2"}

    findings1 = await check.verify(context1, rule_data1)
    findings2 = await check.verify(context2, rule_data2)

    # Both should return lists
    assert isinstance(findings1, list)
    assert isinstance(findings2, list)


def test_knowledge_source_check_policy_file_attribute():
    """Test that the policy_file class attribute is accessible."""
    # This is a class attribute, should be accessible without instantiation
    assert hasattr(KnowledgeSourceCheck, "policy_file")

    # Can also check via instance
    check = KnowledgeSourceCheck()
    assert hasattr(check, "policy_file")


def test_knowledge_source_check_enforcement_methods_structure():
    """Test that enforcement methods are properly structured."""
    check = KnowledgeSourceCheck()

    # Should have enforcement_methods attribute
    assert hasattr(check, "enforcement_methods")

    # Should be a list
    assert isinstance(check.enforcement_methods, list)

    # Should have 5 methods (one for each policy rule)
    assert len(check.enforcement_methods) == 5


@pytest.mark.asyncio
async def test_knowledge_source_check_verify_with_kwargs():
    """Test verify method accepts and handles kwargs."""
    check = KnowledgeSourceCheck()

    context = {}
    rule_data = {}

    # Test with additional keyword arguments
    findings = await check.verify(
        context, rule_data, extra_param="test", another_param=123
    )

    # Should still return a list
    assert isinstance(findings, list)


@pytest.mark.asyncio
async def test_knowledge_source_check_verify_return_type_consistency():
    """Test that verify always returns the same type regardless of input."""
    check = KnowledgeSourceCheck()

    test_cases = [
        ({}, {}),
        ({"key": "value"}, {}),
        ({}, {"rule": "data"}),
        ({"a": 1}, {"b": 2}),
        (None, None),  # Edge case
    ]

    for context, rule_data in test_cases:
        findings = await check.verify(context, rule_data)
        # Always returns a list
        assert isinstance(findings, list)
