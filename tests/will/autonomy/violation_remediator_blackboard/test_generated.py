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
