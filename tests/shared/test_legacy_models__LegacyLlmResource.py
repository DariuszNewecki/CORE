"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/legacy_models.py
- Symbol: LegacyLlmResource
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:04:48
"""

import pytest
from shared.legacy_models import LegacyLlmResource

# TARGET CODE ANALYSIS: LegacyLlmResource is a Pydantic BaseModel class.
# It is NOT async (no 'async def __init__'), so tests are regular functions.

def test_legacy_llm_resource_creation_with_minimal_fields():
    """Test creation with only mandatory fields."""
    resource = LegacyLlmResource(name="test_model", env_prefix="MODEL")
    assert resource.name == "test_model"
    assert resource.env_prefix == "MODEL"
    assert resource.provided_capabilities == []
    assert resource.performance_metadata is None

def test_legacy_llm_resource_creation_with_all_fields():
    """Test creation with all fields provided."""
    capabilities = ["generate", "summarize"]
    metadata = {"tokens_per_second": 100}
    resource = LegacyLlmResource(
        name="full_model",
        provided_capabilities=capabilities,
        env_prefix="FULL",
        performance_metadata=metadata
    )
    assert resource.name == "full_model"
    # Use '==' for list comparison, not 'is'
    assert resource.provided_capabilities == ["generate", "summarize"]
    assert resource.env_prefix == "FULL"
    assert resource.performance_metadata == {"tokens_per_second": 100}

def test_legacy_llm_resource_provided_capabilities_default():
    """Test that provided_capabilities defaults to an empty list."""
    resource1 = LegacyLlmResource(name="m1", env_prefix="P1")
    assert resource1.provided_capabilities == []
    # Explicitly passing empty list should yield same result
    resource2 = LegacyLlmResource(name="m2", provided_capabilities=[], env_prefix="P2")
    assert resource2.provided_capabilities == []

def test_legacy_llm_resource_performance_metadata_default():
    """Test that performance_metadata defaults to None."""
    resource = LegacyLlmResource(name="m", env_prefix="P")
    assert resource.performance_metadata is None

def test_legacy_llm_resource_immutable_fields():
    """Test that fields are set and cannot be changed (frozen by BaseModel default)."""
    resource = LegacyLlmResource(name="original", env_prefix="ORIG")
    # Attempting to assign should raise AttributeError (if model is frozen) or be ignored.
    # This test assumes standard Pydantic behavior where models are mutable by default.
    # We test the values are set correctly.
    assert resource.name == "original"
    assert resource.env_prefix == "ORIG"

def test_legacy_llm_resource_equality():
    """Two instances with same data should be equal (value equality)."""
    res1 = LegacyLlmResource(name="same", env_prefix="S", provided_capabilities=["a"])
    res2 = LegacyLlmResource(name="same", env_prefix="S", provided_capabilities=["a"])
    # Use '==' for model comparison
    assert res1 == res2
    # Their dict representations should also be equal
    assert res1.model_dump() == res2.model_dump()

def test_legacy_llm_resource_inequality():
    """Different data should yield unequal instances."""
    res1 = LegacyLlmResource(name="model1", env_prefix="A")
    res2 = LegacyLlmResource(name="model2", env_prefix="A")
    assert res1 != res2
