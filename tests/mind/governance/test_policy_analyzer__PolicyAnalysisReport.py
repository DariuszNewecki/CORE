"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/policy_analyzer.py
- Symbol: PolicyAnalysisReport
- Status: 5 tests passed, some failed
- Passing tests: test_initialization_with_default_values, test_attribute_types, test_empty_duplicate_and_conflicting_rules, test_rule_distribution_with_multiple_categories, test_total_rules_matches_distribution_sum
- Generated: 2026-01-11 01:30:02
"""

import pytest
from mind.governance.policy_analyzer import PolicyAnalysisReport
from mind.governance.policy_analyzer import AtomicRule

class TestPolicyAnalysisReport:

    def test_initialization_with_default_values(self):
        """Test that PolicyAnalysisReport can be initialized with all default values."""
        report = PolicyAnalysisReport(total_rules=0, duplicate_rules=[], conflicting_rules=[], orphaned_rules=[], rule_distribution={})
        assert report.total_rules == 0
        assert report.duplicate_rules == []
        assert report.conflicting_rules == []
        assert report.orphaned_rules == []
        assert report.rule_distribution == {}

    def test_attribute_types(self):
        """Test that all attributes have the correct types."""
        report = PolicyAnalysisReport(total_rules=5, duplicate_rules=[], conflicting_rules=[], orphaned_rules=[], rule_distribution={'test': 5})
        assert isinstance(report.total_rules, int)
        assert isinstance(report.duplicate_rules, list)
        assert isinstance(report.conflicting_rules, list)
        assert isinstance(report.orphaned_rules, list)
        assert isinstance(report.rule_distribution, dict)

    def test_empty_duplicate_and_conflicting_rules(self):
        """Test that duplicate_rules and conflicting_rules can be empty lists."""
        report = PolicyAnalysisReport(total_rules=3, duplicate_rules=[], conflicting_rules=[], orphaned_rules=[], rule_distribution={'a': 3})
        assert len(report.duplicate_rules) == 0
        assert len(report.conflicting_rules) == 0

    def test_rule_distribution_with_multiple_categories(self):
        """Test that rule_distribution can have multiple categories."""
        report = PolicyAnalysisReport(total_rules=15, duplicate_rules=[], conflicting_rules=[], orphaned_rules=[], rule_distribution={'security': 6, 'privacy': 4, 'compliance': 3, 'operations': 2})
        assert report.rule_distribution['security'] == 6
        assert report.rule_distribution['privacy'] == 4
        assert report.rule_distribution['compliance'] == 3
        assert report.rule_distribution['operations'] == 2
        assert sum(report.rule_distribution.values()) == 15

    def test_total_rules_matches_distribution_sum(self):
        """Test scenario where total_rules matches sum of distribution values."""
        report = PolicyAnalysisReport(total_rules=20, duplicate_rules=[], conflicting_rules=[], orphaned_rules=[], rule_distribution={'a': 8, 'b': 7, 'c': 5})
        distribution_sum = sum(report.rule_distribution.values())
        assert report.total_rules == 20
        assert distribution_sum == 20
