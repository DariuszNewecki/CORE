from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from will.self_healing.remediation_evidence_writer import RemediationEvidenceWriter


@pytest.mark.asyncio
# ID: 2d591305-9b42-49db-b668-9ee8fb92a61e
async def test_write_evidence():
    repo_root = Path("/repo")

    file_handler = MagicMock()
    auditor_context = MagicMock()

    fix_detail = MagicMock()
    fix_detail.finding_id = "F1"
    fix_detail.file_path = "src/a.py"
    fix_detail.action_handler = "handler"
    fix_detail.status = "applied"
    fix_detail.error_message = None
    fix_detail.duration_ms = 12

    result = MagicMock()
    result.session_id = "sess-1"
    result.timestamp_utc = "2024-01-01T00:00:00Z"
    result.total_findings = 3
    result.findings_by_severity = {"high": 2, "low": 1}
    result.matched_patterns = ["p1", "p2"]
    result.unmatched_findings = ["u1"]
    result.fixes_attempted = 2
    result.fixes_succeeded = 1
    result.fixes_failed = 1
    result.validation_passed = False
    result.findings_before = 3
    result.findings_after = 2
    result.improvement_delta = 1
    result.duration_sec = 5.5
    result.audit_input_path = "audit/in.json"
    result.validation_audit_path = "audit/val.json"
    result.fix_details = [fix_detail]

    writer = RemediationEvidenceWriter(
        file_handler=file_handler,
        auditor_context=auditor_context,
        repo_root=repo_root,
    )

    reports_dir = Path("/repo/reports")

    resolver = MagicMock()
    resolver.reports_dir = reports_dir

    resolver_cls = MagicMock()
    resolver_cls.from_repo.return_value = resolver

    with (
        patch(
            "will.self_healing.remediation_evidence_writer.PathResolver",
            resolver_cls,
        ),
        patch(
            "will.self_healing.remediation_evidence_writer.datetime",
        ) as mock_datetime,
    ):
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20240101_120000"
        mock_datetime.now.return_value = mock_now

        evidence_path = await writer.write_evidence(result)

    assert (
        evidence_path
        == reports_dir / "remediation" / "remediation_20240101_120000.json"
    )

    file_handler.ensure_dir.assert_called_once_with("reports/remediation")
    assert file_handler.write_json.call_count == 2

    first_call = file_handler.write_json.call_args_list[0]
    assert first_call.args[0] == "reports/remediation/remediation_20240101_120000.json"
    payload = first_call.args[1]
    assert payload["session_id"] == "sess-1"
    assert payload["matched_count"] == 2
    assert payload["unmatched_count"] == 1

    second_call = file_handler.write_json.call_args_list[1]
    assert second_call.args[0] == "reports/remediation/latest_remediation.json"
    assert second_call.args[1] == payload


@pytest.mark.asyncio
# ID: 36c58ede-1f33-4450-baa5-4c00a51fbef1
async def test_RemediationEvidenceWriter_validate_improvement(tmp_path: Path):
    """The validation audit is a real full audit (#1386).

    It used to call ``AuditorContext.audit()``, which does not exist: the
    except turned every validation into (False, before, None). Here a real
    AuditorContext on a one-file repo runs the real ConstitutionalAuditor
    (stateless: no database, no LLM).
    """
    from mind.governance.audit_context import AuditorContext

    (tmp_path / ".intent").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sample.py").write_text("print('hi')\n", encoding="utf-8")
    writer = RemediationEvidenceWriter(
        file_handler=MagicMock(),
        auditor_context=AuditorContext(tmp_path, stateless=True),
        repo_root=tmp_path,
    )

    passed, findings_after_count, audit_path = await writer.validate_improvement(
        findings_before_count=0
    )

    assert findings_after_count > 0
    assert passed is False
    assert audit_path is not None


# ID: badb4860-e818-479c-8323-a8ad38c21645
def test_RemediationEvidenceWriter_count_by_severity():
    writer = RemediationEvidenceWriter(
        file_handler=MagicMock(),
        auditor_context=MagicMock(),
        repo_root=Path("/tmp/repo"),
    )

    # ID: 88696ab8-8930-415c-8af0-2f3f1fa92025
    def make_finding(severity: str) -> MagicMock:
        finding = MagicMock()
        finding.severity = severity
        return finding

    findings = [
        make_finding("error"),
        make_finding("error"),
        make_finding("warning"),
        make_finding("info"),
        make_finding("info"),
        make_finding("info"),
        make_finding("unknown"),
    ]

    result = writer.count_by_severity(findings)

    assert result == {"error": 2, "warning": 1, "info": 3}


from types import SimpleNamespace


# ID: 01a95b2f-b59e-4380-8345-acf475f88c3e
def test_RemediationEvidenceWriter(tmp_path: Path) -> None:
    file_handler = MagicMock()
    auditor_context = MagicMock()
    repo_root = tmp_path

    writer = RemediationEvidenceWriter(
        file_handler=file_handler,
        auditor_context=auditor_context,
        repo_root=repo_root,
    )

    # --- happy path: count_by_severity ---
    findings = [
        SimpleNamespace(severity="error"),
        SimpleNamespace(severity="error"),
        SimpleNamespace(severity="warning"),
        SimpleNamespace(severity="info"),
        SimpleNamespace(severity="unknown"),
    ]
    counts = writer.count_by_severity(findings)
    assert counts == {"error": 2, "warning": 1, "info": 1}
