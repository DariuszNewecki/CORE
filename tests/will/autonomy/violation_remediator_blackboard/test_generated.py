from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.violation_remediator_blackboard import delegate_capped_findings


# ID: 44ff9805-61d6-4172-89ff-e0bdaef4e0a3
async def test_delegate_capped_findings() -> None:
    service = MagicMock()
    service.query_max_attempt_count_by_subject = AsyncMock(return_value=5)
    service.query_last_failed_proposal_for_subject = AsyncMock(
        return_value={
            "failure_reason": "tests failed",
            "proposal_id": "prop-1",
            "actions": ["a1", "a2"],
        }
    )
    service.delegate_remediation_capped_findings = AsyncMock(return_value=["entry-1"])

    findings = [{"subject": "subj-1", "entry_id": "entry-1"}]

    with patch(
        "will.autonomy.violation_remediator_blackboard._entry_id",
        return_value="entry-1",
    ):
        result = await delegate_capped_findings(service, findings, cap_n=3)

    assert result == ["entry-1"]
    service.query_max_attempt_count_by_subject.assert_awaited_once_with("subj-1")
    service.query_last_failed_proposal_for_subject.assert_awaited_once_with("subj-1")
    service.delegate_remediation_capped_findings.assert_awaited_once()
    call_args = service.delegate_remediation_capped_findings.await_args
    assert call_args.args[0] == ["entry-1"]
    assert call_args.args[1] == 5
    assert call_args.args[2]["attempt_count"] == 5
    assert call_args.args[2]["detail"] == "tests failed"


import pytest

from will.autonomy.violation_remediator_blackboard import mark_delegated


@pytest.mark.asyncio
# ID: 4ae7d5b2-ffd3-4289-984a-21629cb74104
async def test_mark_delegated():
    service = AsyncMock()
    service.mark_indeterminate = AsyncMock(return_value=2)
    findings = [
        {"entry_id": "e1", "decision": "DELEGATE"},
        {"entry_id": "e2", "decision": "DELEGATE"},
    ]

    result = await mark_delegated(service, findings)

    assert result == 2
    service.mark_indeterminate.assert_awaited_once()


import pytest

from will.autonomy.violation_remediator_blackboard import release_unmappable


@pytest.mark.asyncio
# ID: 5be9ddac-e01a-46f6-87db-e7f420d0cf68
async def test_release_unmappable():
    findings = [
        {"entry_id": "entry-1"},
        {"entry_id": "entry-2"},
    ]
    service = AsyncMock()

    with patch(
        "will.autonomy.violation_remediator_blackboard.release_entries",
        new_callable=AsyncMock,
        return_value=2,
    ) as mock_release_entries:
        result = await release_unmappable(service, findings, claimed_by="worker-a")

    assert result == 2
    mock_release_entries.assert_awaited_once_with(
        service, ["entry-1", "entry-2"], claimed_by="worker-a"
    )


import asyncio

from will.autonomy.violation_remediator_blackboard import release_entries


# ID: a30f246e-a714-4d1a-adf6-294afa4b79da
def test_release_entries():
    entry_ids = ["e1", "e2"]
    claimed_by = MagicMock()
    service = MagicMock()
    service.release_claimed_entries = AsyncMock(return_value=2)

    result = asyncio.run(release_entries(service, entry_ids, claimed_by=claimed_by))

    assert result == 2
    service.release_claimed_entries.assert_awaited_once_with(
        entry_ids, claimed_by=claimed_by
    )


import pytest

from will.autonomy.violation_remediator_blackboard import resolve_entries


# ID: 0807cfe1-695a-4948-9c38-e77bcf7a997d
async def test_resolve_entries() -> None:
    service = AsyncMock()
    service.resolve_entries_for_proposal = AsyncMock(return_value=2)

    result = await resolve_entries(service, ["e1", "e2"], "prop-1")

    assert result == 2
    service.resolve_entries_for_proposal.assert_awaited_once_with(
        ["e1", "e2"], "prop-1"
    )




# ID: f45bdecf-d185-4d0d-9fe3-605255cdfd72
async def test_load_open_findings():
    from will.autonomy.violation_remediator_blackboard import load_open_findings

    mappable_finding = {
        "id": "abc",
        "payload": {"check_id": "rule-1", "file_path": "src/app.py"},
    }
    unmappable_finding = {
        "id": "def",
        "payload": {"check_id": "rule-unknown", "file_path": "src/other.py"},
    }

    service = MagicMock()
    service.claim_findings_by_patterns = AsyncMock(
        return_value=[mappable_finding, unmappable_finding]
    )
    service.release_claimed_entries = AsyncMock(return_value=1)
    service.mark_indeterminate = AsyncMock()

    claimed_by = "worker-1"
    remediation_map = {"rule-1": MagicMock()}

    with patch(
        "will.audit_violation.filter.is_autonomously_remediable_target",
        return_value=True,
    ):
        result = await load_open_findings(
            service,
            patterns=["%"],
            claimed_by=claimed_by,
            remediation_map=remediation_map,
        )

    assert result == [mappable_finding]
    service.claim_findings_by_patterns.assert_awaited_once_with(
        patterns=["%"], limit=200, claimed_by=claimed_by
    )
    service.release_claimed_entries.assert_awaited_once()
    service.mark_indeterminate.assert_not_awaited()
