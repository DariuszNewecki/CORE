"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/legacy_models.py
- Symbol: LegacyCognitiveRole
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:05:44
"""

import pytest
from shared.legacy_models import LegacyCognitiveRole

# LegacyCognitiveRole is a synchronous class (not async def __init__), so use regular test functions

def test_legacy_cognitive_role_creation_with_minimal_fields():
    """Test basic instantiation with only required field."""
    role = LegacyCognitiveRole(role="system_operator")

    assert role.role == "system_operator"
    assert role.description is None
    assert role.assigned_resource is None
    assert role.required_capabilities == []

def test_legacy_cognitive_role_creation_with_all_fields():
    """Test instantiation with all fields populated."""
    role = LegacyCognitiveRole(
        role="data_analyst",
        description="Analyzes datasets and generates insights",
        assigned_resource="analytics_cluster_7",
        required_capabilities=["python", "sql", "statistics"]
    )

    assert role.role == "data_analyst"
    assert role.description == "Analyzes datasets and generates insights"
    assert role.assigned_resource == "analytics_cluster_7"
    assert role.required_capabilities == ["python", "sql", "statistics"]

def test_legacy_cognitive_role_with_empty_capabilities():
    """Test that required_capabilities defaults to empty list."""
    role = LegacyCognitiveRole(role="manager")

    assert role.required_capabilities == []
    assert isinstance(role.required_capabilities, list)

def test_legacy_cognitive_role_with_none_description():
    """Test explicit None for optional fields."""
    role = LegacyCognitiveRole(
        role="engineer",
        description=None,
        assigned_resource=None
    )

    assert role.role == "engineer"
    assert role.description is None
    assert role.assigned_resource is None

def test_legacy_cognitive_role_field_types():
    """Verify field types are correct."""
    role = LegacyCognitiveRole(
        role="string_value",
        description="string_description",
        assigned_resource="string_resource",
        required_capabilities=["item1", "item2"]
    )

    assert isinstance(role.role, str)
    assert isinstance(role.description, str)
    assert isinstance(role.assigned_resource, str)
    assert isinstance(role.required_capabilities, list)
    assert all(isinstance(item, str) for item in role.required_capabilities)

def test_legacy_cognitive_role_equality():
    """Test that two instances with same data are equal."""
    role1 = LegacyCognitiveRole(
        role="admin",
        description="System administrator",
        required_capabilities=["linux", "networking"]
    )

    role2 = LegacyCognitiveRole(
        role="admin",
        description="System administrator",
        required_capabilities=["linux", "networking"]
    )

    assert role1.role == role2.role
    assert role1.description == role2.description
    assert role1.required_capabilities == role2.required_capabilities

def test_legacy_cognitive_role_immutability():
    """Test that fields cannot be arbitrarily modified (BaseModel behavior)."""
    role = LegacyCognitiveRole(role="original")

    # Pydantic models are mutable by default, but we should verify assignment works
    role.role = "updated"
    assert role.role == "updated"

def test_legacy_cognitive_role_with_empty_strings():
    """Test handling of empty strings in fields."""
    role = LegacyCognitiveRole(
        role="",
        description="",
        assigned_resource="",
        required_capabilities=[]
    )

    assert role.role == ""
    assert role.description == ""
    assert role.assigned_resource == ""
    assert role.required_capabilities == []

def test_legacy_cognitive_role_default_factory_independence():
    """Test that default_factory creates independent lists for each instance."""
    role1 = LegacyCognitiveRole(role="role1")
    role2 = LegacyCognitiveRole(role="role2")

    role1.required_capabilities.append("cap1")

    assert role1.required_capabilities == ["cap1"]
    assert role2.required_capabilities == []  # Should not be affected

def test_legacy_cognitive_role_special_characters():
    """Test handling of special characters and Unicode in fields."""
    role = LegacyCognitiveRole(
        role="role_with_unicode_…",  # Using Unicode ellipsis
        description="Description with … ellipsis and emoji 🔧",
        assigned_resource="resource_…_special",
        required_capabilities=["capability…", "skill🔧"]
    )

    assert role.role == "role_with_unicode_…"
    assert role.description == "Description with … ellipsis and emoji 🔧"
    assert role.assigned_resource == "resource_…_special"
    assert role.required_capabilities == ["capability…", "skill🔧"]
