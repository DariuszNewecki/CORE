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
