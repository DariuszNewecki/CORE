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


import pytest


@pytest.mark.asyncio
# ID: 04cf154e-6786-4f13-9eea-ff8f26615f68
async def test_AuditClient_audit_remediate():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "dispatched": True})

    client = AuditClient(facade)

    result = await client.audit_remediate("run-123", mode="safe", write=True)

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/audit/remediations",
        json={
            "audit_run_id": "run-123",
            "mode": "safe",
            "write": True,
        },
    )
    assert result == {"status": "ok", "dispatched": True}


import pytest


# ID: 4827649d-1ea6-42ed-bafb-9b7195d89c6f
def test_AuditClient__init__and_audit() -> None:
    import asyncio

    facade = MagicMock()
    facade._request = AsyncMock(
        return_value={"verdict": "pass", "passed": True, "run_id": "abc"}
    )

    client = AuditClient(facade)
    result = asyncio.run(
        client.audit(rule_ids=["r1"], policy_ids=["p1"], files=["f.py"])
    )

    assert result == {"verdict": "pass", "passed": True, "run_id": "abc"}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/audit/runs",
        json={
            "rule_ids": ["r1"],
            "policy_ids": ["p1"],
            "files": ["f.py"],
            "force_llm": False,
            "source": "api",
            "wait": True,
        },
        timeout=1800.0,
    )


# ID: 6a803624-9df6-43cc-92ab-765d8106f929
async def test_AuditClient_audit():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"verdict": "pass", "passed": True})
    client = AuditClient(facade)

    result = await client.audit(
        rule_ids=["r1"],
        policy_ids=["p1"],
        files=["a.py"],
        force_llm=True,
        source="cli",
    )

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/audit/runs",
        json={
            "rule_ids": ["r1"],
            "policy_ids": ["p1"],
            "files": ["a.py"],
            "force_llm": True,
            "source": "cli",
            "wait": True,
        },
        timeout=1800.0,
    )
    assert result == {"verdict": "pass", "passed": True}


import asyncio


# ID: 0b80a1a9-9be1-4f3a-830a-1efa3d8bf5ab
def test_AuditClient():
    from api.cli.audit_client import AuditClient

    facade = MagicMock()
    facade._request = AsyncMock(return_value={"verdict": "pass", "run_id": "r1"})
    facade._poll_at_path = AsyncMock(return_value={"status": "completed"})

    client = AuditClient(facade)

    result = asyncio.run(
        client.audit(
            rule_ids=["R1"],
            policy_ids=["P1"],
            files=["f.py"],
            force_llm=True,
            source="api",
        )
    )

    assert result == {"verdict": "pass", "run_id": "r1"}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/audit/runs",
        json={
            "rule_ids": ["R1"],
            "policy_ids": ["P1"],
            "files": ["f.py"],
            "force_llm": True,
            "source": "api",
            "wait": True,
        },
        timeout=1800.0,
    )
