from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.autonomy.proposal_execution_pipeline import rollback_proposal


# ID: 871ae9a7-ca53-4eda-9126-cab5a6294595
def test_rollback_proposal():
    git_service = MagicMock()
    git_service.restore_paths = MagicMock(return_value=[])

    action_results = {"paths": ["src/a.py", "src/b.py"]}

    with patch(
        "will.autonomy.proposal_execution_pipeline.compute_production_set",
        return_value=["src/a.py", "src/b.py"],
    ) as mock_compute:
        result = rollback_proposal(
            git_service=git_service,
            proposal_id="prop-123",
            action_results=action_results,
            pre_sha="abcdef1234567890",
        )

    assert result is None
    mock_compute.assert_called_once_with(action_results)
    git_service.restore_paths.assert_called_once_with(
        ["src/a.py", "src/b.py"], source="abcdef1234567890"
    )


from unittest.mock import AsyncMock

import pytest

from will.autonomy.proposal_execution_pipeline import resolve_deferred_findings


@pytest.mark.asyncio
# ID: aa626ee3-65b3-4169-99b3-fdb180480ab2
async def test_resolve_deferred_findings():
    mock_bb_service = AsyncMock()
    mock_bb_service.resolve_deferred_entries_for_completed_proposal = AsyncMock(
        return_value={"resolved_count": 3}
    )

    with patch(
        "body.services.service_registry.service_registry.get_blackboard_service",
        new=AsyncMock(return_value=mock_bb_service),
    ):
        result = await resolve_deferred_findings("prop-123")

    assert result is True
    mock_bb_service.resolve_deferred_entries_for_completed_proposal.assert_awaited_once_with(
        "prop-123"
    )


from will.autonomy.proposal_execution_pipeline import capture_git_sha


# ID: 34eb9510-319c-479e-bbf6-f5980cddfb42
def test_capture_git_sha():
    git_service = MagicMock()
    git_service.get_current_commit.return_value = "abc123def456"

    result = capture_git_sha(git_service, phase="pre", proposal_id="prop-1")

    assert result == "abc123def456"
    git_service.get_current_commit.assert_called_once_with()


from will.autonomy.proposal_execution_pipeline import CommitOutcome


# ID: 3d17b98a-8997-485c-9c62-c3e8728af149
def test_CommitOutcome():
    assert CommitOutcome.COMMITTED.value == "committed"
    assert CommitOutcome.NOTHING_TO_COMMIT.value == "nothing_to_commit"
    assert CommitOutcome.REFUSED_CONTAMINATION == "refused_contamination"
    assert CommitOutcome.FAILED.value == "failed"

    assert isinstance(CommitOutcome.COMMITTED, str)
    assert len(list(CommitOutcome)) == 4


from will.autonomy.proposal_execution_pipeline import compute_production_set


# ID: e248409a-a084-4210-8b0b-f0fa71e0ae59
def test_compute_production_set():
    action_results = {
        "action_a": {
            "data": {
                "_sandbox_target_paths": ["src/pkg/a.py", "src/pkg/b.py"],
                "files_produced": ["src/pkg/c.py"],
            }
        },
        "action_b": {
            "data": {
                "_sandbox_target_paths": ["src/pkg/b.py"],
                "files_produced": ["src/pkg/d.py", ""],
            }
        },
        "action_c": {
            "data": {
                "_sandbox_target_paths": ["src/pkg/a.py", 123, None],
                "files_produced": [],
            }
        },
    }

    result = compute_production_set(action_results)

    assert result == [
        "src/pkg/a.py",
        "src/pkg/b.py",
        "src/pkg/c.py",
        "src/pkg/d.py",
    ]


# ID: 6eb6ff9e-7d1e-4dac-b2e1-67643b9a370d
def test_commit_proposal_changes():
    from will.autonomy.proposal_execution_pipeline import commit_proposal_changes

    git_service = MagicMock()
    action_results = {
        "action_1": {
            "_sandbox_target_paths": ["src/foo.py"],
            "files_produced": ["src/bar.py"],
        }
    }

    with (
        patch(
            "will.autonomy.proposal_execution_pipeline.compute_production_set",
            return_value=["src/foo.py", "src/bar.py"],
        ) as mock_compute,
        patch(
            "will.autonomy.proposal_execution_pipeline.autonomous_identity",
            return_value="core-identity",
        ) as mock_autonomous_identity,
        patch(
            "will.autonomy.proposal_execution_pipeline.producer_identity",
            return_value="producer-identity",
        ) as mock_producer_identity,
    ):
        outcome = commit_proposal_changes(
            git_service=git_service,
            proposal_id="abcdef0123456789deadbeef",
            proposal_goal="do the thing",
            action_results=action_results,
            producer="some-producer",
        )

    from will.autonomy.proposal_execution_pipeline import CommitOutcome

    assert outcome == CommitOutcome.COMMITTED
    mock_compute.assert_called_once_with(action_results)
    git_service.commit_paths.assert_called_once_with(
        ["src/foo.py", "src/bar.py"],
        "fix(abcdef0123456789): do the thing",
        identity="core-identity",
        author="producer-identity",
    )
    mock_producer_identity.assert_called_once_with("some-producer")


import pytest

from will.autonomy.proposal_execution_pipeline import compute_changed_files


@pytest.mark.asyncio
# ID: 567a42b4-0a3c-4a7d-b09a-87d62cab8a0b
async def test_compute_changed_files():
    git_service = MagicMock()
    git_service.diff_file_names = AsyncMock(return_value=["a.py", "b.py"])

    result = await compute_changed_files(
        git_service=git_service,
        pre_sha="abc123",
        post_sha="def456",
        proposal_id="prop-1",
    )

    assert result == ["a.py", "b.py"]
    git_service.diff_file_names.assert_awaited_once_with("abc123", "def456")


import pytest

from will.autonomy.proposal_execution_pipeline import record_consequence


@pytest.mark.asyncio
# ID: 14d8aa1a-f570-443d-b297-e388e963554f
async def test_record_consequence():
    mock_svc = MagicMock()
    mock_svc.record = AsyncMock(return_value=None)

    with patch(
        "will.autonomy.proposal_execution_pipeline.service_registry.get_consequence_log_service",
        new=AsyncMock(return_value=mock_svc),
    ):
        result = await record_consequence(
            proposal_id="prop-123",
            pre_sha="abc123",
            post_sha="def456",
            changed_files=["a.py", "b.py"],
            finding_ids=["f1", "f2"],
            policies=["rule-1"],
            declared_production=["c.py"],
            source="execution",
        )

    assert result is True
    mock_svc.record.assert_awaited_once_with(
        proposal_id="prop-123",
        pre_execution_sha="abc123",
        post_execution_sha="def456",
        files_changed=[{"path": "a.py"}, {"path": "b.py"}],
        findings_resolved=["f1", "f2"],
        authorized_by_rules=["rule-1"],
        declared_production=["c.py"],
        consequence_source="execution",
    )


from will.autonomy.proposal_execution_pipeline import consequence_finding_ids


# ID: 4287d9b4-44b3-4718-8b9a-650545bb1d45
def test_consequence_finding_ids():
    constraints = {
        "finding_ids": ["f1", "f2"],
        "addressed_finding_ids": ["f2", "f3"],
    }
    result = consequence_finding_ids(constraints)
    assert result == ["f1", "f2", "f3"]


import pytest

from will.autonomy.proposal_execution_pipeline import revive_deferred_findings_for_noop


@pytest.mark.asyncio
# ID: 43ca4fd7-12af-4f21-afc0-735f99915b90
async def test_revive_deferred_findings_for_noop():
    mock_config = MagicMock()
    mock_config.blackboard.remediation_cap_n = 3

    mock_bb_service = MagicMock()
    mock_bb_service.revive_or_delegate_findings_for_noop_proposal = AsyncMock(
        return_value={"revived_count": 2, "delegated_count": 1}
    )

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_bb_service)

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=mock_config,
        ),
        patch(
            "body.services.service_registry.service_registry",
            mock_registry,
        ),
        patch(
            "will.autonomy.proposal_execution_pipeline.service_registry",
            mock_registry,
            create=True,
        ),
    ):
        adjudicated, revival = await revive_deferred_findings_for_noop("proposal-123")

    assert adjudicated is True
    assert revival == {"revived_count": 2, "delegated_count": 1}
    mock_bb_service.revive_or_delegate_findings_for_noop_proposal.assert_awaited_once()
    call_kwargs = (
        mock_bb_service.revive_or_delegate_findings_for_noop_proposal.await_args.kwargs
    )
    assert call_kwargs["proposal_id"] == "proposal-123"
    assert call_kwargs["remediation_cap_n"] == 3
