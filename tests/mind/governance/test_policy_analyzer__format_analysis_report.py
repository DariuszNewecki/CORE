"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/policy_analyzer.py
- Symbol: format_analysis_report
- Status: 1 tests passed, some failed
- Passing tests: test_empty_report
- Generated: 2026-01-11 01:33:14
"""

import pytest
from mind.governance.policy_analyzer import format_analysis_report

class TestFormatAnalysisReport:

    def test_empty_report(self):
        """Test formatting with an empty report."""
        from mind.governance.policy_analyzer import PolicyAnalysisReport
        report = PolicyAnalysisReport(total_rules=0, duplicate_rules=[], conflicting_rules=[], orphaned_rules=[], rule_distribution={})
        result = format_analysis_report(report)
        assert isinstance(result, str)
        assert 'CONSTITUTIONAL POLICY ANALYSIS REPORT' in result
        assert 'Total Rules: 0' in result
        assert 'Duplicate Rules: 0' in result
        assert 'Conflicting Rules: 0' in result
        assert 'Orphaned Rules: 0' in result
        assert 'Rule Distribution by Enforcement Method:' in result
        assert '⚠️  DUPLICATE RULES' not in result
        assert '❌ CONFLICTING RULES' not in result
