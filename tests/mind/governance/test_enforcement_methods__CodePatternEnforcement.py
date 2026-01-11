"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/enforcement_methods.py
- Symbol: CodePatternEnforcement
- Status: 4 tests passed, some failed
- Passing tests: test_verify_correct_detection, test_verify_all_required_patterns_present, test_verify_severity_passed_to_findings, test_verify_default_severity
- Generated: 2026-01-11 01:42:01
"""

import pytest
from mind.governance.enforcement_methods import CodePatternEnforcement
from mind.governance.enforcement_methods import AuditFinding, AuditSeverity
from typing import Any

def test_verify_correct_detection():
    """Test when detection is correctly configured."""
    enforcer = CodePatternEnforcement(rule_id='test_rule')
    context = None
    rule_data = {'detection': {'method': 'ast_call_scan', 'patterns': ['os.system', 'subprocess.run']}}
    findings = enforcer.verify(context, rule_data)
    assert len(findings) == 0

def test_verify_all_required_patterns_present():
    """Test when all required patterns are present."""
    enforcer = CodePatternEnforcement(rule_id='test_rule', required_patterns=['dangerous.call', 'unsafe.exec'])
    context = None
    rule_data = {'detection': {'method': 'ast_call_scan', 'patterns': ['dangerous.call', 'unsafe.exec', 'extra.pattern']}}
    findings = enforcer.verify(context, rule_data)
    assert len(findings) == 0

def test_verify_severity_passed_to_findings():
    """Test that severity from constructor is used in findings."""
    enforcer = CodePatternEnforcement(rule_id='test_rule', severity=AuditSeverity.WARNING)
    context = None
    rule_data = {}
    findings = enforcer.verify(context, rule_data)
    assert len(findings) == 1
    assert findings[0].severity == AuditSeverity.WARNING

def test_verify_default_severity():
    """Test that default severity (ERROR) is used when not specified."""
    enforcer = CodePatternEnforcement(rule_id='test_rule')
    context = None
    rule_data = {}
    findings = enforcer.verify(context, rule_data)
    assert len(findings) == 1
    assert findings[0].severity == AuditSeverity.ERROR
