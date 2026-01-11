"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/rule_extractor.py
- Symbol: extract_executable_rules
- Status: 9 tests passed, some failed
- Passing tests: test_extract_executable_rules_basic_extraction, test_extract_executable_rules_multiple_rules, test_extract_executable_rules_missing_enforcement_mapping, test_extract_executable_rules_invalid_policy_structure, test_extract_executable_rules_enforcement_mapping_missing_engine, test_extract_executable_rules_scope_handling, test_extract_executable_rules_empty_policies, test_extract_executable_rules_scope_fallback, test_extract_executable_rules_rule_without_id
- Generated: 2026-01-11 01:55:16
"""

import pytest
from mind.governance.rule_extractor import extract_executable_rules

def test_extract_executable_rules_basic_extraction():
    """Test basic rule extraction with valid enforcement mapping"""
    policies = {'policy1': {'rules': [{'id': 'rule1', 'statement': 'Files must have proper headers', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'pre-commit'}]}}
    loader = TestEnforcementMappingLoader({'rule1': {'engine': 'regex_checker', 'params': {'pattern': '^# Copyright'}, 'scope': {'applies_to': ['src/**/*.py'], 'excludes': ['tests/']}}})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 1
    rule = result[0]
    assert rule.rule_id == 'rule1'
    assert rule.engine == 'regex_checker'
    assert rule.enforcement == 'mandatory'
    assert rule.statement == 'Files must have proper headers'
    assert rule.scope == ['src/**/*.py']
    assert rule.exclusions == ['tests/']
    assert rule.policy_id == 'policy1'
    assert rule.is_context_level is False

def test_extract_executable_rules_multiple_rules():
    """Test extraction with multiple rules across policies"""
    policies = {'policy1': {'rules': [{'id': 'rule1', 'statement': 'Rule one', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'audit'}]}, 'policy2': {'rules': [{'id': 'rule2', 'statement': 'Rule two', 'enforcement': 'reporting', 'authority': 'quality', 'phase': 'audit'}]}}
    loader = TestEnforcementMappingLoader({'rule1': {'engine': 'engine1', 'params': {}}, 'rule2': {'engine': 'engine2', 'params': {}}})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 2
    rule_ids = {r.rule_id for r in result}
    assert rule_ids == {'rule1', 'rule2'}

def test_extract_executable_rules_missing_enforcement_mapping():
    """Test rules without enforcement mappings are skipped"""
    policies = {'policy1': {'rules': [{'id': 'rule1', 'statement': 'Has mapping', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'audit'}, {'id': 'rule2', 'statement': 'No mapping', 'enforcement': 'reporting', 'authority': 'quality', 'phase': 'audit'}]}}
    loader = TestEnforcementMappingLoader({'rule1': {'engine': 'engine1', 'params': {}}})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 1
    assert result[0].rule_id == 'rule1'

def test_extract_executable_rules_invalid_policy_structure():
    """Test handling of invalid policy structures"""
    policies = {'policy1': 'not a dict', 'policy2': {'rules': 'not a list'}, 'policy3': {'rules': [{'id': 'rule1'}]}, 'policy4': {'rules': [{'id': 'rule4', 'statement': 'Valid rule', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'audit'}]}}
    loader = TestEnforcementMappingLoader({'rule4': {'engine': 'engine1', 'params': {}}})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 1
    assert result[0].rule_id == 'rule4'

def test_extract_executable_rules_enforcement_mapping_missing_engine():
    """Test enforcement mappings without engine field"""
    policies = {'policy1': {'rules': [{'id': 'rule1', 'statement': 'Rule without engine', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'audit'}]}}
    loader = TestEnforcementMappingLoader({'rule1': {'params': {'key': 'value'}}})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 0

def test_extract_executable_rules_scope_handling():
    """Test various scope format handling"""
    policies = {'policy1': {'rules': [{'id': 'rule1', 'statement': 'Test scope', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'audit'}]}}
    loader = TestEnforcementMappingLoader({'rule1': {'engine': 'engine1', 'params': {}, 'scope': {'applies_to': 'src/**/*.py', 'excludes': 'tests/'}}})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 1
    assert result[0].scope == ['src/**/*.py']
    assert result[0].exclusions == ['tests/']

def test_extract_executable_rules_empty_policies():
    """Test with empty policies dictionary"""
    policies = {}
    loader = TestEnforcementMappingLoader({})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 0

def test_extract_executable_rules_scope_fallback():
    """Test fallback scope when scope data is not a dict"""
    policies = {'policy1': {'rules': [{'id': 'rule1', 'statement': 'Test fallback', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'audit'}]}}
    loader = TestEnforcementMappingLoader({'rule1': {'engine': 'engine1', 'params': {}, 'scope': 'invalid'}})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 1
    assert result[0].scope == ['src/**/*.py']
    assert result[0].exclusions == []

def test_extract_executable_rules_rule_without_id():
    """Test rules without ID are skipped"""
    policies = {'policy1': {'rules': [{'statement': 'No ID', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'audit'}, {'id': 'rule2', 'statement': 'With ID', 'enforcement': 'mandatory', 'authority': 'security', 'phase': 'audit'}]}}
    loader = TestEnforcementMappingLoader({'rule2': {'engine': 'engine1', 'params': {}}})
    result = extract_executable_rules(policies, loader)
    assert len(result) == 1
    assert result[0].rule_id == 'rule2'
