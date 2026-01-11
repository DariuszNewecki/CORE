"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/schemas.py
- Symbol: GovernanceRegistry
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:00:15
"""

from mind.governance.schemas import GovernanceRegistry


# TARGET CODE ANALYSIS:
# - GovernanceRegistry is a regular class, not async.
# - All methods are synchronous getters and listers.
# - Return types are: PolicyResource | None, PatternResource | None,
#   ConstitutionalPrinciple | None, and list[str].


def test_governance_registry_initialization():
    """Test that a new registry is empty."""
    registry = GovernanceRegistry()
    assert registry.policies == {}
    assert registry.patterns == {}
    assert registry.principles == {}


def test_get_policy_exists():
    """Test retrieving a policy that exists."""
    registry = GovernanceRegistry()
    # Simulate adding a policy (since we cannot import PolicyResource for real data)
    # We'll test the dict access directly as the method is a simple wrapper.
    test_policy = object()  # Stand-in for a PolicyResource
    registry.policies["test-policy-1"] = test_policy

    result = registry.get_policy("test-policy-1")
    assert result == test_policy


def test_get_policy_not_exists():
    """Test retrieving a policy that does not exist returns None."""
    registry = GovernanceRegistry()
    result = registry.get_policy("non-existent-id")
    assert result is None


def test_get_pattern_exists():
    """Test retrieving a pattern that exists."""
    registry = GovernanceRegistry()
    test_pattern = object()  # Stand-in for a PatternResource
    registry.patterns["test-pattern-1"] = test_pattern

    result = registry.get_pattern("test-pattern-1")
    assert result == test_pattern


def test_get_pattern_not_exists():
    """Test retrieving a pattern that does not exist returns None."""
    registry = GovernanceRegistry()
    result = registry.get_pattern("non-existent-id")
    assert result is None


def test_get_principle_exists():
    """Test retrieving a principle that exists."""
    registry = GovernanceRegistry()
    test_principle = object()  # Stand-in for a ConstitutionalPrinciple
    registry.principles["test-principle-1"] = test_principle

    result = registry.get_principle("test-principle-1")
    assert result == test_principle


def test_get_principle_not_exists():
    """Test retrieving a principle that does not exist returns None."""
    registry = GovernanceRegistry()
    result = registry.get_principle("non-existent-id")
    assert result is None


def test_list_policies():
    """Test listing all policy IDs."""
    registry = GovernanceRegistry()
    registry.policies["policy-a"] = object()
    registry.policies["policy-b"] = object()

    result = registry.list_policies()
    # Order is not guaranteed by dict.keys() in all Python versions, but list() preserves insertion order.
    assert result == ["policy-a", "policy-b"]


def test_list_policies_empty():
    """Test listing policies when none are loaded."""
    registry = GovernanceRegistry()
    result = registry.list_policies()
    assert result == []


def test_list_patterns():
    """Test listing all pattern IDs."""
    registry = GovernanceRegistry()
    registry.patterns["pattern-x"] = object()
    registry.patterns["pattern-y"] = object()

    result = registry.list_patterns()
    assert result == ["pattern-x", "pattern-y"]


def test_list_patterns_empty():
    """Test listing patterns when none are loaded."""
    registry = GovernanceRegistry()
    result = registry.list_patterns()
    assert result == []


def test_list_principles():
    """Test listing all principle IDs."""
    registry = GovernanceRegistry()
    registry.principles["principle-1"] = object()
    registry.principles["principle-2"] = object()

    result = registry.list_principles()
    assert result == ["principle-1", "principle-2"]


def test_list_principles_empty():
    """Test listing principles when none are loaded."""
    registry = GovernanceRegistry()
    result = registry.list_principles()
    assert result == []
