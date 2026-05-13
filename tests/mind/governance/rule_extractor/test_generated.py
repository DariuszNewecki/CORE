from src.mind.governance.rule_extractor import (
    _topologically_sort_rules,
    extract_executable_rules,
)

import pytest

# Mock objects to simulate dependencies
class EnforcementMappingLoader:
    pass

# Define a test class for the rule_extractor module
class TestRuleExtractor:
    # Test case 1: Topological sort rules
    def test_topologically_sort_rules(self):
        rules = [
            ExecutableRule(rule_id="rule1", requires_findings_from=["rule2"]),
            ExecutableRule(rule_id="rule2"),
        ]
        expected_output = [ExecutableRule("rule2"), ExecutableRule("rule1")]
        assert _topologically_sort_rules(rules) == expected_output

    # Test case 2: Extract executable rules
    def test_extract_executable_rules(self):
        policies = {
            "policy1": {"name": "Policy1", "implementations": ["impl1"]},
            "policy2": {"name": "Policy2"},
        }
        enforcement_loader = EnforcementMappingLoader()
        expected_output = [
            ExecutableRule(
                rule_id="rule1",
                requires_findings_from=["rule2"],
                canonical_rule={"name": "Policy1", "implementations": ["impl1"]},
                enforcement_mapping={},
            ),
            ExecutableRule(
                rule_id="rule2",
                canonical_rule={"name": "Policy2"},
                enforcement_mapping={},
            ),
        ]
        assert extract_executable_rules(policies, enforcement_loader) == expected_output
