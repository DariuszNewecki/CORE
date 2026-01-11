"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/audit_postprocessor.py
- Symbol: apply_entry_point_downgrade_and_report
- Status: 6 tests passed, some failed
- Passing tests: test_no_downgrade_wrong_rule_id, test_no_downgrade_missing_symbol_key, test_no_downgrade_not_in_allow_list, test_no_downgrade_already_low_severity, test_empty_string_handling, test_write_reports_without_file_handler_raises
- Generated: 2026-01-11 02:04:37
"""

import pytest
from pathlib import Path
from mind.governance.audit_postprocessor import apply_entry_point_downgrade_and_report

def test_no_downgrade_wrong_rule_id():
    """Test that non-dead-public-symbol findings are not downgraded."""
    findings = [{'rule_id': 'other_rule', 'symbol_key': 'module.function', 'severity': 'error', 'message': 'test finding'}]
    symbol_index = {'module.function': {'entry_point_type': 'cli', 'pattern_name': 'main'}}
    result = apply_entry_point_downgrade_and_report(findings=findings, symbol_index=symbol_index, write_reports=False)
    assert result[0]['severity'] == 'error'

def test_no_downgrade_missing_symbol_key():
    """Test that findings without symbol_key are not processed."""
    findings = [{'rule_id': 'dead_public_symbol', 'severity': 'error', 'message': 'test finding'}]
    symbol_index = {}
    result = apply_entry_point_downgrade_and_report(findings=findings, symbol_index=symbol_index, write_reports=False)
    assert result[0]['severity'] == 'error'

def test_no_downgrade_not_in_allow_list():
    """Test that entry points not in allow list are not downgraded."""
    findings = [{'rule_id': 'dead_public_symbol', 'symbol_key': 'module.function', 'severity': 'error', 'message': 'test finding'}]
    symbol_index = {'module.function': {'entry_point_type': 'not_allowed', 'pattern_name': 'unknown'}}
    result = apply_entry_point_downgrade_and_report(findings=findings, symbol_index=symbol_index, write_reports=False)
    assert result[0]['severity'] == 'error'

def test_no_downgrade_already_low_severity():
    """Test that info severity findings are not modified."""
    findings = [{'rule_id': 'dead_public_symbol', 'symbol_key': 'module.function', 'severity': 'info', 'message': 'test finding'}]
    symbol_index = {'module.function': {'entry_point_type': 'cli', 'pattern_name': 'main'}}
    result = apply_entry_point_downgrade_and_report(findings=findings, symbol_index=symbol_index, write_reports=False)
    assert result[0]['severity'] == 'info'

def test_empty_string_handling():
    """Test handling of empty strings in metadata."""
    findings = [{'rule_id': 'dead_public_symbol', 'symbol_key': 'module.function', 'severity': 'error', 'message': 'test finding'}]
    symbol_index = {'module.function': {'entry_point_type': '', 'pattern_name': '', 'entry_point_justification': ''}}
    result = apply_entry_point_downgrade_and_report(findings=findings, symbol_index=symbol_index, write_reports=False)
    assert result[0]['severity'] == 'error'

def test_write_reports_without_file_handler_raises():
    """Test that write_reports=True without file_handler raises ValueError."""
    findings = [{'rule_id': 'dead_public_symbol', 'symbol_key': 'module.function', 'severity': 'error', 'message': 'test finding'}]
    symbol_index = {'module.function': {'entry_point_type': 'cli', 'pattern_name': 'main'}}
    with pytest.raises(ValueError, match='write_reports=True requires file_handler'):
        apply_entry_point_downgrade_and_report(findings=findings, symbol_index=symbol_index, write_reports=True)
