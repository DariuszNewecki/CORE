from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from will.governance.audit_remediation_runner import run_and_persist_audit_remediation


@pytest.mark.asyncio
# ID: 5f7c4977-e9c4-4058-bc2b-3b6d68b5cde1
async def test_run_and_persist_audit_remediation():
    session = MagicMock()
    run_id = uuid4()

    context = MagicMock()
    context.auditor_context = MagicMock()
    context.file_service = MagicMock()
    context.git_service.repo_path = "/tmp/repo"

    result = MagicMock()
    result.total_findings = 5
    result.fixes_attempted = 3
    result.fixes_succeeded = 2
    result.improvement_delta = 1.5
    result.validation_passed = True
    result.findings_before = 5
    result.findings_after = 3
    result.duration_sec = 1.23
    result.audit_input_path = "/tmp/audit.json"
    result.remediation_output_path = "/tmp/remediation.json"
    result.validation_audit_path = "/tmp/validation.json"

    mock_service = MagicMock()
    mock_service.remediate = AsyncMock(return_value=result)

    with (
        patch(
            "will.governance.audit_remediation_runner.resolve_mode",
            return_value="safe",
        ),
        patch(
            "will.governance.audit_remediation_runner.AuditRemediationService",
            return_value=mock_service,
        ),
        patch(
            "will.governance.audit_remediation_runner._update_remediation_run_status",
            new=AsyncMock(),
        ) as mock_update,
    ):
        await run_and_persist_audit_remediation(
            context,
            session,
            run_id=run_id,
            mode="safe",
            write=True,
        )

    mock_service.remediate.assert_awaited_once_with(mode="safe", write=True)

    assert mock_update.await_count == 2
    first_call = mock_update.await_args_list[0]
    assert first_call.args[1] == run_id
    assert first_call.args[2] == "executing"

    last_call = mock_update.await_args_list[-1]
    assert last_call.args[1] == run_id
    assert last_call.args[2] == "completed"
    assert last_call.kwargs["finished"] is True
    assert last_call.kwargs["error"] is None
    assert last_call.kwargs["result"]["fixes_succeeded"] == 2
