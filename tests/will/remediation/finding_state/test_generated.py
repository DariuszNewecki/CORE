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


import pytest

from will.remediation.finding_state import query_file_attempt_count


@pytest.mark.asyncio
# ID: a756ec79-61aa-425d-9be4-3d588e22fb8d
async def test_query_file_attempt_count():
    mock_svc = AsyncMock()
    mock_svc.query_max_attempt_count_by_file_path = AsyncMock(return_value=3)
    mock_registry = AsyncMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_svc)

    with patch("body.services.service_registry.service_registry", mock_registry):
        result = await query_file_attempt_count("/some/file.py")

    assert result == 3
    mock_registry.get_blackboard_service.assert_awaited_once()
    mock_svc.query_max_attempt_count_by_file_path.assert_awaited_once_with(
        "/some/file.py"
    )


import pytest

from will.remediation.finding_state import abandon_findings


@pytest.mark.asyncio
# ID: f4d4ed35-f3e9-49de-8625-90427c8f3f5b
async def test_abandon_findings():
    findings = [{"id": "123"}, {"id": 456}]

    mock_svc = MagicMock()
    mock_svc.abandon_entries_and_increment_attempt_count = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_svc)

    with patch("body.services.service_registry.service_registry", mock_registry):
        await abandon_findings(findings)

    mock_registry.get_blackboard_service.assert_awaited_once()
    mock_svc.abandon_entries_and_increment_attempt_count.assert_awaited_once_with(
        ["123", "456"]
    )


import uuid


# ID: ff980a99-7892-4c27-9a6d-623415abb85d
async def test_release_findings() -> None:
    from will.remediation.finding_state import release_findings

    claimed_by = uuid.uuid4()
    findings = [{"id": "a1"}, {"id": "b2"}]

    mock_svc = AsyncMock()
    mock_svc.release_claimed_entries = AsyncMock(return_value=None)

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_svc)

    with patch("body.services.service_registry.service_registry", mock_registry):
        await release_findings(findings, claimed_by=claimed_by)

    mock_registry.get_blackboard_service.assert_awaited_once()
    mock_svc.release_claimed_entries.assert_awaited_once_with(
        ["a1", "b2"], claimed_by=claimed_by
    )


from uuid import uuid4

import pytest

from will.remediation.finding_state import claim_unmapped_findings


@pytest.mark.asyncio
# ID: 5b3544c1-aba7-40db-99fa-4fca69d3a3fe
async def test_claim_unmapped_findings():
    claimed_by = uuid4()
    mapped_rule_ids = {"rule-1", "rule-2"}
    limit = 10

    finding = {
        "id": str(uuid4()),
        "payload": {"file_path": "src/foo/bar.py"},
    }

    mock_svc = MagicMock()
    mock_svc.claim_unmapped_violation_findings = AsyncMock(return_value=[finding])
    mock_svc.mark_indeterminate = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_svc)

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "shared.infrastructure.intent.audit_namespaces.audit_violation_like_patterns",
            return_value=["%audit%"],
        ),
        patch(
            "will.audit_violation.filter.is_autonomously_remediable_target",
            return_value=True,
        ),
    ):
        result = await claim_unmapped_findings(
            mapped_rule_ids, claimed_by=claimed_by, limit=limit
        )

    assert result == [finding]
    mock_svc.claim_unmapped_violation_findings.assert_awaited_once_with(
        mapped_rule_ids=mapped_rule_ids,
        patterns=["%audit%"],
        limit=limit,
        claimed_by=claimed_by,
    )
    mock_svc.mark_indeterminate.assert_not_awaited()
