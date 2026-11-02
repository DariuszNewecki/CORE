from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: c2e7bbe3-4beb-428c-8885-774817193383
async def test_run_and_record_probes():
    from will.orchestration.goal_run_probes import run_and_record_probes

    worker = MagicMock()
    worker._context = MagicMock()
    worker.goal = "some-goal"
    worker.workflow_type = "goal_run"
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    worker.probe_records = None

    records = [
        {"probe": "alpha", "passed": True},
        {"probe": "beta", "passed": True},
    ]

    with (
        patch(
            "will.orchestration.goal_run_probes.run_apparatus_probes",
            new=AsyncMock(return_value=records),
        ) as mock_run_probes,
        patch(
            "will.orchestration.goal_run_probes.blackboard_safe",
            side_effect=lambda r: r,
        ),
    ):
        result = await run_and_record_probes(worker, "run-123")

    assert result is True
    mock_run_probes.assert_awaited_once_with(worker._context, "run-123")
    assert worker.probe_records == records
    assert worker.post_report.await_count == 2
    worker.post_observation.assert_not_awaited()


import pytest

from will.orchestration.goal_run_probes import run_apparatus_probes


@pytest.mark.asyncio
# ID: 44d0b910-167f-44f9-bcbd-80e83aa59e69
async def test_run_apparatus_probes():
    context = object()
    run_id = "run-123"

    record_i5 = {"probe": "I-5", "run_id": run_id, "passed": True}
    record_i6 = {"probe": "I-6", "run_id": run_id, "passed": True}

    mock_i5 = AsyncMock(return_value=record_i5)
    mock_i6 = AsyncMock(return_value=record_i6)

    with (
        patch("will.orchestration.goal_run_probes.run_probe_i5", mock_i5),
        patch("will.orchestration.goal_run_probes.run_probe_i6", mock_i6),
    ):
        result = await run_apparatus_probes(context, run_id)

    assert result == [record_i5, record_i6]
    mock_i5.assert_awaited_once_with(context, run_id)
    mock_i6.assert_awaited_once_with(context, run_id)


import pytest

from will.orchestration.goal_run_probes import run_probe_i6


@pytest.mark.asyncio
# ID: 36d4f47e-1fc1-41b4-9ca6-32c2a0f7e2cc
async def test_run_probe_i6():
    from will.autonomy.proposal import ProposalStatus
    from will.autonomy.safe_auto_approval_envelope import SafeAutoApprovalDeniedError

    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    service_registry = MagicMock()
    service_registry.session = MagicMock(return_value=session_ctx)

    repo = MagicMock()
    repo.create = AsyncMock(return_value="proposal-123")

    # Build the denial error via the real class signature (single message arg).
    denial_exc = SafeAutoApprovalDeniedError("denied by safe auto-approval envelope")

    manager = MagicMock()
    manager.approve = AsyncMock(side_effect=denial_exc)

    with (
        patch("body.services.service_registry.service_registry", service_registry),
        patch(
            "will.autonomy.proposal_repository.ProposalRepository", return_value=repo
        ),
        patch(
            "will.autonomy.proposal_state_manager.ProposalStateManager",
            return_value=manager,
        ),
        patch(
            "will.orchestration.goal_run_probes._proposal_status",
            AsyncMock(return_value=ProposalStatus.PENDING.value),
        ),
        patch(
            "will.orchestration.goal_run_probes.rule_in_bound_law",
            return_value={"loaded": True},
        ),
    ):
        result = await run_probe_i6(context=MagicMock(), run_id="run-abc")

    assert result["proposal_id"] == "proposal-123"
    assert result["result"]["approved"] is False
    assert result["result"]["denial"] is not None
    assert result["result"]["proposal_status_after"] == ProposalStatus.PENDING.value


from types import SimpleNamespace

import pytest

from will.orchestration.goal_run_probes import (
    CONTAINMENT_RULE_ID,
    PROBE_I5,
    run_probe_i5,
)


@pytest.mark.asyncio
# ID: 60db86d1-f09a-482c-a7a9-f0d4722b2963
async def test_run_probe_i5(tmp_path):
    subject_root = tmp_path / "subject"
    subject_root.mkdir()

    binding = SimpleNamespace(
        subject_path=str(subject_root),
        bound_repo_path=str(tmp_path),
    )
    context = SimpleNamespace(target_binding=binding)

    refusal = {"rule_id": CONTAINMENT_RULE_ID}
    result = SimpleNamespace(
        ok=False,
        data={
            "error": "refused",
            "error_type": "containment",
            "rule_id": CONTAINMENT_RULE_ID,
            "refusal": refusal,
        },
    )

    executor_instance = MagicMock()
    executor_instance.execute = AsyncMock(return_value=result)

    with (
        patch(
            "body.atomic.executor.ActionExecutor", return_value=executor_instance
        ) as mock_executor_cls,
        patch(
            "will.orchestration.goal_run_probes.rule_in_bound_law",
            return_value={"loaded": True},
        ) as mock_rule_in_bound_law,
    ):
        record = await run_probe_i5(context, run_id="run-123")

    mock_executor_cls.assert_called_once_with(context)
    executor_instance.execute.assert_awaited_once()
    call_kwargs = executor_instance.execute.await_args.kwargs
    assert call_kwargs["action_id"] == "file.create"
    assert call_kwargs["write"] is True
    assert call_kwargs["file_path"] == str(
        subject_root.resolve() / "_core_probe_I-5.py"
    )

    mock_rule_in_bound_law.assert_called_once_with(CONTAINMENT_RULE_ID)

    assert record["probe"] == PROBE_I5
    assert record["run_id"] == "run-123"
    assert record["expected_rule_id"] == CONTAINMENT_RULE_ID
    assert record["attempt"]["bound_repo_path"] == str(tmp_path)
    assert record["result"]["ok"] is False
    assert record["result"]["rule_id"] == CONTAINMENT_RULE_ID
    assert record["result"]["refusal"] == refusal
    assert record["artefact_exists_after"] is False
    assert record["rule_in_bound_law"] == {"loaded": True}
    assert record["passed"] is True
    assert "reason" not in record


from pathlib import Path


# ID: e924027d-50cb-44cd-b8ac-e84ffe607d8e
def test_rule_in_bound_law():
    from will.orchestration.goal_run_probes import rule_in_bound_law

    root = Path("/execution/copy/.intent")
    source_path = root / "laws" / "governance.md"

    ref = SimpleNamespace(
        source_path=str(source_path),
        rule_content_hash="abc123hash",
    )
    mock_repo = MagicMock()
    mock_repo.root = root
    mock_repo.get_rule.return_value = ref

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        result = rule_in_bound_law("ADR-133")

    mock_repo.get_rule.assert_called_once_with("ADR-133")
    assert result == {
        "loaded": True,
        "rule_id": "ADR-133",
        "document": str(Path("laws") / "governance.md"),
        "content_hash": "abc123hash",
    }
