"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/auditor.py
- Symbol: ConstitutionalAuditor
- Status: 3 tests passed, some failed
- Passing tests: test_init_creates_directories, test_write_findings_returns_path, test_write_audit_evidence_returns_path
- Generated: 2026-01-11 01:48:04
"""

from pathlib import Path
from unittest.mock import Mock, patch

from mind.governance.auditor import ConstitutionalAuditor


class TestConstitutionalAuditor:

    def test_init_creates_directories(self):
        """Test that __init__ creates required report directories."""
        mock_context = Mock()
        mock_fs = Mock()
        with patch("mind.governance.auditor.FileHandler", return_value=mock_fs):
            auditor = ConstitutionalAuditor(mock_context)
            assert auditor.context == mock_context
            assert auditor.fs == mock_fs
            mock_fs.ensure_dir.assert_any_call("reports")
            mock_fs.ensure_dir.assert_any_call("reports/audit")

    def test_write_findings_returns_path(self):
        """Test _write_findings writes findings and returns path."""
        mock_context = Mock()
        mock_fs = Mock()
        auditor = ConstitutionalAuditor(mock_context)
        auditor.fs = mock_fs
        mock_finding = Mock()
        mock_finding.as_dict = Mock(return_value={"test": "data"})
        findings = [mock_finding]
        with (
            patch("mind.governance.auditor.REPORTS_DIR", Path("/test/reports")),
            patch("mind.governance.auditor.FINDINGS_FILENAME", "findings.json"),
            patch(
                "mind.governance.auditor._repo_rel",
                return_value="reports/findings.json",
            ),
        ):
            result = auditor._write_findings(findings)
            assert isinstance(result, Path)
            assert str(result) == "/test/reports/findings.json"
            mock_fs.write_runtime_json.assert_called_once_with(
                "reports/findings.json", [{"test": "data"}]
            )

    def test_write_audit_evidence_returns_path(self):
        """Test _write_audit_evidence writes evidence and returns path."""
        mock_context = Mock()
        mock_fs = Mock()
        auditor = ConstitutionalAuditor(mock_context)
        auditor.fs = mock_fs
        executed_rules = {"rule1", "rule2"}
        findings_path = Path("/test/findings.json")
        processed_findings_path = Path("/test/processed.json")
        with (
            patch("mind.governance.auditor.AUDIT_EVIDENCE_DIR", Path("/test/audit")),
            patch("mind.governance.auditor.AUDIT_EVIDENCE_FILENAME", "evidence.json"),
            patch(
                "mind.governance.auditor._repo_rel", side_effect=lambda x: str(x.name)
            ),
            patch(
                "mind.governance.auditor._utc_now_iso",
                return_value="2024-01-01T00:00:00Z",
            ),
        ):
            result = auditor._write_audit_evidence(
                executed_rules=executed_rules,
                findings_path=findings_path,
                processed_findings_path=processed_findings_path,
                passed=True,
            )
            assert isinstance(result, Path)
            assert str(result) == "/test/audit/evidence.json"
            mock_fs.write_runtime_json.assert_called_once()
            call_args = mock_fs.write_runtime_json.call_args[0]
            assert call_args[0] == "evidence.json"
            payload = call_args[1]
            assert payload["schema_version"] == "0.2.0"
            assert payload["generated_at_utc"] == "2024-01-01T00:00:00Z"
            assert payload["passed"]
            assert payload["executed_rules"] == ["rule1", "rule2"]
            assert payload["artifacts"]["findings"] == "findings.json"
            assert payload["artifacts"]["processed_findings"] == "processed.json"
