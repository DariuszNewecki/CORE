from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ID: 9bd5e011-9973-4207-b4d5-ea136a897fe6
def test_check_audited_commit():
    from will.audit_violation.staleness import check_audited_commit

    audited = MagicMock()
    audited.behind = True
    audited.audited = "abc123"
    audited.upstream = "def456"

    git_service = MagicMock()
    core_context = MagicMock()
    core_context.git_service = git_service
    blackboard = MagicMock()
    core_context.registry.get_blackboard_service = AsyncMock(return_value=blackboard)

    worker = MagicMock()

    with (
        patch(
            "will.audit_violation.staleness.audited_commit", return_value=audited
        ) as mock_audited_commit,
        patch(
            "body.infrastructure.repo_sync.upstream_branch", return_value="origin/main"
        ),
        patch(
            "will.audit_violation.staleness.guard_stale_audit", new_callable=AsyncMock
        ) as mock_guard,
    ):
        result_audited, result_behind = asyncio.run(
            check_audited_commit(worker, core_context, behind_cycles=2)
        )

    assert result_audited is audited
    assert result_behind == 3
    mock_audited_commit.assert_called_once_with(git_service, "origin/main")
    core_context.registry.get_blackboard_service.assert_awaited_once()
    mock_guard.assert_awaited_once_with(worker, blackboard, audited, 3)


import pytest

from will.audit_violation.staleness import (
    STALE_AFTER_CYCLES,
    STALE_SUBJECT,
    guard_stale_audit,
)


@pytest.mark.asyncio
# ID: 3d47cba4-9499-457d-b238-ac57fa868cdc
async def test_guard_stale_audit() -> None:
    worker = MagicMock()
    worker.post_observation = AsyncMock()

    blackboard = MagicMock()
    blackboard.fetch_active_finding_subjects_by_prefix = AsyncMock(return_value=set())
    blackboard.adjudicate_indeterminate_findings = AsyncMock()

    state = MagicMock()
    state.behind = True
    state.as_payload = MagicMock(return_value={"sha": "abc123"})

    await guard_stale_audit(
        worker=worker,
        blackboard=blackboard,
        state=state,
        behind_cycles=STALE_AFTER_CYCLES,
    )

    blackboard.fetch_active_finding_subjects_by_prefix.assert_awaited_once_with(
        STALE_SUBJECT
    )
    worker.post_observation.assert_awaited_once()
    _, kwargs = worker.post_observation.await_args
    assert kwargs["subject"] == STALE_SUBJECT
    assert kwargs["status"] == "indeterminate"
    assert kwargs["payload"]["cycles_behind"] == STALE_AFTER_CYCLES
    blackboard.adjudicate_indeterminate_findings.assert_not_awaited()


from will.audit_violation.staleness import audited_commit


# ID: 35c945ec-b898-433c-b6c3-441b4dcbfd46
def test_audited_commit():
    git_service = MagicMock()
    git_service.get_current_commit.return_value = "abc123"
    git_service.resolve_ref.return_value = "def456"
    git_service.is_ancestor.return_value = True

    result = audited_commit(git_service, "main")

    git_service.get_current_commit.assert_called_once_with()
    git_service.resolve_ref.assert_called_once_with("refs/remotes/upstream/main")
    attrs = {k: getattr(result, k) for k in dir(result) if not k.startswith("_")}
    values = [
        getattr(result, name) for name in attrs if not callable(getattr(result, name))
    ]
    assert "abc123" in values
    assert "def456" in values or "abc123" in values


from will.audit_violation.staleness import AuditedCommit


# ID: c6aee2bc-2c53-4215-b8af-9413c9c6ce7e
def test_AuditedCommit_as_payload():
    record = MagicMock(spec=AuditedCommit)
    record.audited = "abc123"
    record.upstream = "def456"
    record.behind = 3

    payload = AuditedCommit.as_payload(record)

    assert payload == {
        "audited_commit": "abc123",
        "upstream_commit": "def456",
        "behind_upstream": 3,
    }




# ID: 27f75f92-a6be-456d-bd34-b3d5a3f62a1d
def test_AuditedCommit_behind():
    commit = AuditedCommit(audited="abc123", upstream="def456")
    assert commit.behind is True

    commit = AuditedCommit(audited="abc123", upstream="abc123")
    assert commit.behind is False

    commit = AuditedCommit(audited="", upstream="def456")
    assert commit.behind is False
