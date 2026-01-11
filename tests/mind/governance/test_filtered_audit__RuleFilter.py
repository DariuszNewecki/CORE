"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/filtered_audit.py
- Symbol: RuleFilter
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:48:54
"""

from mind.governance.filtered_audit import RuleFilter


# Detected return type: RuleFilter.matches() returns bool


class TestRuleFilter:
    def test_init_with_no_arguments(self):
        """Test initialization with default empty filters."""
        filter = RuleFilter()
        assert filter.rule_ids == set()
        assert filter.policy_ids == set()
        assert filter.rule_patterns == []

    def test_init_with_rule_ids(self):
        """Test initialization with rule_ids."""
        filter = RuleFilter(rule_ids=["rule1", "rule2"])
        assert filter.rule_ids == {"rule1", "rule2"}
        assert filter.policy_ids == set()
        assert len(filter.rule_patterns) == 0

    def test_init_with_policy_ids(self):
        """Test initialization with policy_ids."""
        filter = RuleFilter(policy_ids=["policy1", "policy2"])
        assert filter.rule_ids == set()
        assert filter.policy_ids == {"policy1", "policy2"}
        assert len(filter.rule_patterns) == 0

    def test_init_with_rule_patterns(self):
        """Test initialization with rule_patterns."""
        filter = RuleFilter(rule_patterns=["^test.*", ".*rule$"])
        assert filter.rule_ids == set()
        assert filter.policy_ids == set()
        assert len(filter.rule_patterns) == 2

    def test_matches_with_no_filters(self):
        """Test matches() returns True when no filters are set."""
        filter = RuleFilter()

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        rule1 = MockRule("any_rule", "any_policy")
        rule2 = MockRule("another_rule", "another_policy")

        assert filter.matches(rule1)
        assert filter.matches(rule2)

    def test_matches_rule_id_exact_match(self):
        """Test matches() with rule_id filter."""
        filter = RuleFilter(rule_ids=["specific_rule", "another_rule"])

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        matching_rule = MockRule("specific_rule", "any_policy")
        non_matching_rule = MockRule("different_rule", "any_policy")

        assert filter.matches(matching_rule)
        assert not filter.matches(non_matching_rule)

    def test_matches_policy_id_exact_match(self):
        """Test matches() with policy_id filter."""
        filter = RuleFilter(policy_ids=["specific_policy", "another_policy"])

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        matching_rule = MockRule("any_rule", "specific_policy")
        non_matching_rule = MockRule("any_rule", "different_policy")

        assert filter.matches(matching_rule)
        assert not filter.matches(non_matching_rule)

    def test_matches_rule_pattern_match(self):
        """Test matches() with rule pattern filter."""
        filter = RuleFilter(rule_patterns=["^test_.*", ".*_prod$"])

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        rule1 = MockRule("test_rule_1", "any_policy")
        rule2 = MockRule("service_prod", "any_policy")
        rule3 = MockRule("dev_service", "any_policy")

        assert filter.matches(rule1)
        assert filter.matches(rule2)
        assert not filter.matches(rule3)

    def test_matches_multiple_filters_any_can_match(self):
        """Test matches() when multiple filter types are set."""
        filter = RuleFilter(
            rule_ids=["exact_rule"],
            policy_ids=["exact_policy"],
            rule_patterns=[".*pattern.*"],
        )

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        rule_by_id = MockRule("exact_rule", "other_policy")
        rule_by_policy = MockRule("other_rule", "exact_policy")
        rule_by_pattern = MockRule("has_pattern_in_it", "other_policy")
        non_matching_rule = MockRule("no_match", "no_match")

        assert filter.matches(rule_by_id)
        assert filter.matches(rule_by_policy)
        assert filter.matches(rule_by_pattern)
        assert not filter.matches(non_matching_rule)

    def test_matches_case_sensitive_ids(self):
        """Test that rule_id and policy_id matches are case-sensitive."""
        filter = RuleFilter(rule_ids=["MyRule"], policy_ids=["MyPolicy"])

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        lowercase_rule = MockRule("myrule", "mypolicy")
        uppercase_rule = MockRule("MyRule", "MyPolicy")

        assert not filter.matches(lowercase_rule)
        assert filter.matches(uppercase_rule)

    def test_matches_pattern_case_sensitive_by_default(self):
        """Test that regex patterns are case-sensitive by default."""
        filter = RuleFilter(rule_patterns=["^Test"])

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        lowercase_rule = MockRule("test_rule", "any")
        uppercase_rule = MockRule("Test_rule", "any")

        assert not filter.matches(lowercase_rule)
        assert filter.matches(uppercase_rule)

    def test_matches_empty_string_pattern(self):
        """Test matches() with empty string pattern."""
        filter = RuleFilter(rule_patterns=[""])

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        rule = MockRule("any_rule", "any_policy")

        # Empty pattern matches beginning of any string
        assert filter.matches(rule)

    def test_matches_partial_pattern_match(self):
        """Test that pattern.match() requires match at beginning of string."""
        filter = RuleFilter(rule_patterns=["middle"])

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        rule_with_middle = MockRule("has_middle_text", "any")

        # pattern.match() requires match at beginning, so this should be False
        assert not filter.matches(rule_with_middle)

    def test_matches_full_string_pattern(self):
        """Test pattern that matches entire string."""
        filter = RuleFilter(rule_patterns=["^complete_match$"])

        class MockRule:
            def __init__(self, rule_id, policy_id):
                self.rule_id = rule_id
                self.policy_id = policy_id

        exact_match = MockRule("complete_match", "any")
        partial_match = MockRule("complete_match_extra", "any")

        assert filter.matches(exact_match)
        assert not filter.matches(partial_match)
