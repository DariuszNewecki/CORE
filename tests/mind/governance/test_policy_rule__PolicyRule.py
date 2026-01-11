"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/policy_rule.py
- Symbol: PolicyRule
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:20:21
"""

from mind.governance.policy_rule import PolicyRule


# TARGET CODE ANALYSIS:
# - PolicyRule.from_dict is a classmethod (sync, not async).
# - It parses a dictionary into a PolicyRule instance.
# - It has default values for many fields.
# - The 'check' block extraction handles dict or non-dict types.
# - Pattern is derived from 'scope' list (first item) or 'pattern' field.
# - All test functions should be regular 'def', not async.


def test_from_dict_basic_required_fields():
    """Test parsing with minimal required fields."""
    data = {
        "id": "test.rule",
        "statement": "A test description.",
        "enforcement": "error",
        "scope": ["src/**/*.py"],
    }
    rule = PolicyRule.from_dict(data, source="test_policy.yaml")
    assert rule.name == "test.rule"
    assert rule.pattern == "src/**/*.py"
    assert rule.action == "deny"  # default from data.get("action") or "deny"
    assert rule.description == "A test description."
    assert rule.severity == "error"
    assert rule.source_policy == "test_policy.yaml"
    assert rule.engine is None
    assert rule.params == {}


def test_from_dict_with_full_fields_and_check_block():
    """Test parsing with all fields including engine check block."""
    data = {
        "name": "custom.name",
        "description": "Full rule.",
        "action": "warn",
        "severity": "warning",
        "scope": ["lib/**/*.js", "test/**/*.js"],
        "check": {
            "engine": "ast_gate",
            "params": {"check_type": "import_boundary", "allowed": ["lib"]},
        },
    }
    rule = PolicyRule.from_dict(data, source="full.json")
    assert rule.name == "custom.name"
    assert rule.pattern == "lib/**/*.js"  # first scope entry
    assert rule.action == "warn"
    assert rule.description == "Full rule."
    assert rule.severity == "warning"
    assert rule.source_policy == "full.json"
    assert rule.engine == "ast_gate"
    assert rule.params == {"check_type": "import_boundary", "allowed": ["lib"]}


def test_from_dict_fallbacks_and_missing_data():
    """Test fallback logic when fields are missing or empty."""
    # Empty dict
    rule1 = PolicyRule.from_dict({})
    assert rule1.name == "unnamed"
    assert rule1.pattern == ""
    assert rule1.action == "deny"
    assert rule1.description == ""
    assert rule1.severity == "error"
    assert rule1.source_policy == "unknown"
    assert rule1.engine is None
    assert rule1.params == {}

    # 'id' instead of 'name', 'statement' instead of 'description'
    data2 = {
        "id": "fallback.id",
        "statement": "A statement.",
        "enforcement": "warning",
        # No scope or pattern
    }
    rule2 = PolicyRule.from_dict(data2)
    assert rule2.name == "fallback.id"
    assert rule2.pattern == ""
    assert rule2.description == "A statement."
    assert rule2.severity == "warning"

    # 'pattern' field instead of 'scope'
    data3 = {"pattern": "docs/*.md"}
    rule3 = PolicyRule.from_dict(data3)
    assert rule3.pattern == "docs/*.md"

    # 'scope' is a single string? (should become list first element? Actually code expects list)
    # The code does isinstance(scope, list). If scope is a string, it will fail that check.
    # Let's test that scenario: scope is a non-list.
    data4 = {"scope": "single_string_scope"}
    rule4 = PolicyRule.from_dict(data4)
    # scope is not a list, so pattern becomes "" (empty string).
    assert rule4.pattern == ""


def test_from_dict_check_block_non_dict():
    """Test that a non-dict 'check' block is handled safely."""
    data = {
        "id": "weird.check",
        "scope": ["a.py"],
        "check": "not_a_dict",  # This will make isinstance(check_block, dict) False
    }
    rule = PolicyRule.from_dict(data)
    assert rule.engine is None
    assert rule.params == {}  # Because check_block is not a dict, params defaults to {}


def test_from_dict_source_parameter():
    """Test that the source parameter is correctly assigned."""
    data = {"scope": ["x"]}
    rule = PolicyRule.from_dict(data, source="custom_source")
    assert rule.source_policy == "custom_source"

    rule2 = PolicyRule.from_dict(data)  # default source
    assert rule2.source_policy == "unknown"


def test_policyrule_instance_attributes():
    """Test that a PolicyRule instance can be created directly (not just from_dict)."""
    rule = PolicyRule(
        name="direct.rule",
        pattern="*.txt",
        action="deny",
        description="Direct instantiation.",
        severity="error",
        source_policy="direct",
        engine="regex_engine",
        params={"regex": ".*"},
    )
    assert rule.name == "direct.rule"
    assert rule.pattern == "*.txt"
    assert rule.action == "deny"
    assert rule.description == "Direct instantiation."
    assert rule.severity == "error"
    assert rule.source_policy == "direct"
    assert rule.engine == "regex_engine"
    assert rule.params == {"regex": ".*"}


def test_from_dict_with_empty_scope_list():
    """Test that an empty scope list results in empty pattern."""
    data = {"scope": []}
    rule = PolicyRule.from_dict(data)
    assert rule.pattern == ""


def test_from_dict_scope_list_with_non_string_first_item():
    """Test that first scope item is converted to string."""
    data = {"scope": [123, "*.py"]}
    rule = PolicyRule.from_dict(data)
    assert rule.pattern == "123"  # str(123)
