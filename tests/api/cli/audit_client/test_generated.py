from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.audit_client import AuditClient


@pytest.mark.asyncio
# ID: 07f45f64-21b6-4536-b38f-0172dd632131
async def test_AuditClient_poll_audit_remediation_run():
    facade = MagicMock()
    facade._poll_at_path = AsyncMock(return_value={"status": "completed"})

    client = AuditClient(facade)

    result = await client.poll_audit_remediation_run("run-123", timeout_seconds=42.0)

    assert result == {"status": "completed"}
    facade._poll_at_path.assert_awaited_once_with(
        "/v1/audit/remediations/run-123", timeout_seconds=42.0
    )


import pytest


@pytest.mark.asyncio
# ID: 8f21ec2f-fdc9-4216-8f10-f734edc13840
async def test_AuditClient_get_audit_remediation_run():
    facade = MagicMock()
    facade._request = AsyncMock(
        return_value={"run_id": "run-123", "status": "completed"}
    )

    client = AuditClient(facade)
    result = await client.get_audit_remediation_run("run-123")

    facade._request.assert_awaited_once_with("GET", "/v1/audit/remediations/run-123")
    assert result == {"run_id": "run-123", "status": "completed"}
