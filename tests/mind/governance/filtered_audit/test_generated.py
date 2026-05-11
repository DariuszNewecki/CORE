import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import re

from src.mind.governance.filtered_audit import RuleFilter, normalize_file_filter, run_filtered_audit
from src.mind.constitution import ExecutableRule


class TestRuleFilter:
    """Test suite for RuleFilter class."""

    def test_init_empty_filters(self):
        """Test initialization with all default None parameters."""
        filter_obj = RuleFilter()
        assert filter_obj.rule_ids == set()
        assert filter_obj.policy_ids == set()
        assert filter_obj.rule_patterns == []

    def test_init_with_explicit_none(self):
        """Test initialization with explicit None for all parameters."""
        filter_obj = RuleFilter(rule_ids=None, policy_ids=None, rule_patterns=None)
        assert filter_obj.rule_ids == set()
        assert filter_obj.policy_ids == set()
        assert filter_obj.rule_patterns == []

    def test_init_with_all_filters(self):
        """Test initialization with all filter parameters provided."""
        filter_obj = RuleFilter(
            rule_ids=["rule1", "rule2"],
            policy_ids=["policy_a"],
            rule_patterns=["RUL.*"]
        )
        assert filter_obj.rule_ids == {"rule1", "rule2"}
        assert filter_obj.policy_ids == {"policy_a"}
        assert len(filter_obj.rule_patterns) == 1
        assert isinstance(filter_obj.rule_patterns[0], re.Pattern)

    def test_init_converts_list_to_set(self):
        """Test that rule_ids and policy_ids are converted to sets."""
        filter_obj = RuleFilter(rule_ids=["dup", "dup"], policy_ids=["same", "same"])
        assert filter_obj.rule_ids == {"dup"}
        assert filter_obj.policy_ids == {"same"}

    def test_init_compiles_patterns(self):
        """Test that rule_patterns are compiled to regex patterns."""
        filter_obj = RuleFilter(rule_patterns=["test.*", ".*spec$"])
        assert all(isinstance(p, re.Pattern) for p in filter_obj.rule_patterns)
        assert filter_obj.rule_patterns[0].pattern == "test.*"
        assert filter_obj.rule_patterns[1].pattern == ".*spec$"

    def test_matches_no_filters_returns_true(self):
        """Test matches returns True when no filters are set."""
        filter_obj = RuleFilter()
        rule = MagicMock(spec=ExecutableRule)
        rule.rule_id = "any_rule"
        rule.policy_id = "any_policy"
        assert filter_obj.matches(rule) is True

    def test_matches_exact_rule_id(self):
        """Test matches returns True for exact rule ID match."""
        filter_obj = RuleFilter(rule_ids=["target_rule"])
        rule = MagicMock(spec=ExecutableRule)
        rule.rule_id = "target_rule"
        rule.policy_id = "other_policy"
        assert filter_obj.matches(rule) is True

    def test_matches_non_matching_rule_id(self):
        """Test matches returns False for non-matching rule ID."""
        filter_obj = RuleFilter(rule_ids=["target_rule"])
        rule = MagicMock(spec=ExecutableRule)
        rule.rule_id = "other_rule"
        rule.policy_id = "other_policy"
        assert filter_obj.matches(rule) is False

    def test_matches_policy_id(self):
        """Test matches returns True for matching policy ID."""
        filter_obj = RuleFilter(policy_ids=["security_policy"])
        rule = MagicMock(spec=ExecutableRule)
        rule.rule_id = "some_rule"
        rule.policy_id = "security_policy"
        assert filter_obj.matches(rule) is True

    def test_matches_non_matching_policy_id(self):
        """Test matches returns False for non-matching policy ID."""
        filter_obj = RuleFilter(policy_ids=["security_policy"])
        rule = MagicMock(spec=ExecutableRule)
        rule.rule_id = "some_rule"
        rule.policy_id = "other_policy"
        assert filter_obj.matches(rule) is False

    def test_matches_pattern(self):
        """Test matches returns True when rule_id matches regex pattern."""
        filter_obj = RuleFilter(rule_patterns=["^CONS-[0-9]+$"])
        rule = MagicMock(spec=ExecutableRule)
        rule.rule_id = "CONS-001"
        rule.policy
