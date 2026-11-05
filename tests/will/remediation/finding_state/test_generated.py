from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.remediation.finding_state import delegate_capped_findings


@pytest.mark.asyncio
# ID: 1f37e894-b684-4f9b-ae3a-35af38c2870a
async def test_delegate_capped_findings():
    entry_ids = ["e1", "e2"]
    count = 3
    file_path = "src/foo.py"

    mock_svc = MagicMock()
    mock_svc.fetch_latest_report_payload = AsyncMock(
        return_value={"reason": "some prior reason"}
    )
    mock_svc.delegate_remediation_capped_findings = AsyncMock(return_value=None)

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_svc)

    with patch("body.services.service_registry.service_registry", mock_registry):
        await delegate_capped_findings(entry_ids, count, file_path)

    mock_registry.get_blackboard_service.assert_awaited_once()

    mock_svc.fetch_latest_report_payload.assert_awaited_once_with(
        f"audit.remediation.failed::{file_path}"
    )

    mock_svc.delegate_remediation_capped_findings.assert_awaited_once_with(
        entry_ids,
        count,
        {
            "reason": "failure_cap_delegated",
            "detail": "some prior reason",
            "attempted_actions": "llm_remediation_ceremony",
            "attempt_count": count,
        },
    )
