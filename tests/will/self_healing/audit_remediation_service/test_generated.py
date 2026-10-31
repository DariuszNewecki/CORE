from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from will.self_healing.audit_remediation_service import AuditRemediationService


# ID: 35739a88-6d2e-471f-a6b5-faf169bc208d
async def test_AuditRemediationService_remediate():
    from will.self_healing.audit_remediation_service import RemediationMode

    repo_root = Path("/tmp/repo")
    file_handler = MagicMock()
    auditor_context = MagicMock()

    with (
        patch(
            "will.self_healing.audit_remediation_service.PathResolver"
        ) as mock_path_resolver_cls,
        patch(
            "will.self_healing.audit_remediation_service.RemediationPatternMatcher"
        ) as mock_matcher_cls,
        patch(
            "will.self_healing.audit_remediation_service.RemediationExecutor"
        ) as mock_executor_cls,
        patch(
            "will.self_healing.audit_remediation_service.RemediationEvidenceWriter"
        ) as mock_evidence_cls,
    ):
        mock_path_resolver = MagicMock()
        mock_path_resolver_cls.return_value = mock_path_resolver

        mock_matcher = MagicMock()
        mock_matcher.patterns = []
        mock_matched = [MagicMock()]
        mock_unmatched = [MagicMock()]
        mock_matcher.match = MagicMock(return_value=(mock_matched, mock_unmatched))
        mock_matcher_cls.return_value = mock_matcher

        mock_executor = MagicMock()
        mock_fix_details = [MagicMock()]
        mock_executor.execute = AsyncMock(return_value=mock_fix_details)
        mock_executor_cls.return_value = mock_executor

        mock_evidence = MagicMock()
        mock_evidence.count_by_severity = MagicMock(return_value={"high": 1})
        mock_evidence.write_evidence = AsyncMock(
            return_value=Path("/tmp/evidence.json")
        )
        mock_evidence_cls.return_value = mock_evidence

        service = AuditRemediationService(
            file_handler=file_handler,
            auditor_context=auditor_context,
            repo_root=repo_root,
        )

        findings = [MagicMock(), MagicMock()]
        service._load_findings = AsyncMock(return_value=findings)
        service._default_findings_path = MagicMock(
            return_value=Path("/tmp/findings.json")
        )

        mock_result = MagicMock()
        mock_result.fixes_succeeded = 1
        mock_result.fixes_attempted = 1
        mock_result.improvement_delta = 0
        mock_result.validation_passed = False

        with patch(
            "will.self_healing.audit_remediation_service.create_remediation_result",
            return_value=mock_result,
        ) as mock_create_result:
            result = await service.remediate(write=False)

    assert result is mock_result
    service._load_findings.assert_awaited_once()
    mock_matcher.match.assert_called_once_with(
        findings, RemediationMode.SAFE_ONLY, None
    )
    mock_executor.execute.assert_awaited_once_with(mock_matched, False)
    mock_evidence.write_evidence.assert_awaited_once_with(mock_result)
    mock_create_result.assert_called_once()
    assert mock_result.remediation_output_path == "/tmp/evidence.json"
