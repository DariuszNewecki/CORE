from __future__ import annotations

import uuid
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.remediation.ceremony import RemediationCeremony
from will.remediation.models import _RemediationPlan


_WORKER_UUID = uuid.uuid4()


def _make_ceremony(worker_uuid: uuid.UUID | None = None) -> RemediationCeremony:
    """worker_uuid defaults to None (ADR-154 D3a shape: no real worker
    identity — CLI file-mode, candidate-export-only). D3-specific tests
    pass worker_uuid=_WORKER_UUID explicitly to reach
    _create_ceremony_draft instead."""
    ctx = MagicMock()
    ctx.action_executor = AsyncMock()
    blackboard = AsyncMock()
    blackboard.worker_uuid = worker_uuid
    return RemediationCeremony(
        core_context=ctx,
        target_rule="rule.a",
        blackboard=blackboard,
    )


def _plan(file_path: str = "pkg/mod.py") -> _RemediationPlan:
    return _RemediationPlan(
        file_path=file_path,
        original_source="x = 1\n",
        baseline_sha="base-sha",
        violations_summary="[]",
        architectural_context={},
        context_text="",
    )


_FINDINGS = [{"id": "f1", "payload": {"rule": "rule.a", "file_path": "pkg/mod.py"}}]


def _patch_submit_and_persist_fix(ok: bool, run_id: str = "run-123", error: str = "x"):
    """Patch will.remediation.ceremony's imported submit_and_persist_fix,
    returning (validation_run_id, ActionResult-shaped mock)."""
    result = MagicMock(ok=ok, data={} if ok else {"error": error})
    return patch(
        "will.remediation.ceremony.submit_and_persist_fix",
        new=AsyncMock(return_value=(run_id, result)),
    )


# --- _collect_rule_ids (ADR-154 D1 provenance) ---


# ID: 0eecf188-a062-428d-80c9-3190e9bbd384
def test_collect_rule_ids_dedupes_and_sorts() -> None:
    ceremony = _make_ceremony()
    findings = [
        {"payload": {"rule": "rule.b"}},
        {"payload": {"rule": "rule.a"}},
        {"payload": {"rule": "rule.a"}},
    ]
    assert ceremony._collect_rule_ids(findings) == ["rule.a", "rule.b"]


# ID: 0225a29c-4be5-4ba8-bb0f-3c4fa78ec804
def test_collect_rule_ids_none_on_missing_rule() -> None:
    """A finding with no resolvable rule must fail the collection entirely —
    never silently substitute 'unknown' into a set assisted.validate_diff
    will actually check."""
    ceremony = _make_ceremony()
    findings = [{"payload": {"rule": "rule.a"}}, {"payload": {}}]
    assert ceremony._collect_rule_ids(findings) is None


# --- _execute_file fail-closed gate (ADR-154 D1) ---


@pytest.mark.asyncio
# ID: cf65d3ab-89da-411b-837e-da1126effc3e
async def test_execute_file_blocks_on_failed_validation() -> None:
    """Canary passes, assisted.validate_diff fails -> candidate/PENDING
    construction must never run. A failed gate cannot be silently
    bypassed."""
    ceremony = _make_ceremony()

    with (
        patch.object(ceremony, "_check_atomic_action_coverage", return_value=None),
        patch.object(ceremony, "_invoke_llm", new=AsyncMock(return_value="fixed")),
        patch.object(ceremony, "_pack_crate", new=AsyncMock(return_value="crate-1")),
        patch.object(ceremony, "_align_staged_file", new=AsyncMock(return_value=None)),
        patch.object(ceremony, "_run_canary", new=AsyncMock(return_value=True)),
        patch.object(
            ceremony,
            "_generate_patch",
            new=AsyncMock(return_value="--- a/x\n+++ b/x\n"),
        ),
        _patch_submit_and_persist_fix(ok=False, error="rule.a still fires"),
    ):
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is False
    ceremony._ctx.git_service.commit_paths.assert_not_called()
    ceremony._blackboard.post_observation.assert_not_called()
    ceremony._blackboard.mark_findings.assert_awaited_with(_FINDINGS, "abandoned")
    post_failed_call = ceremony._blackboard.post_failed.await_args
    assert "assisted.validate_diff failed" in post_failed_call.args[3]
    assert "run-123" in post_failed_call.args[3]


@pytest.mark.asyncio
# ID: 998f72b4-96f1-43c6-bc61-4aeb3a291144
async def test_execute_file_empty_patch_fails_without_calling_validate_diff() -> None:
    """No-op candidate (empty/unavailable diff) is its own precondition
    failure — it must never reach assisted.validate_diff at all, and must
    not invent a new finding disposition beyond the existing 'abandoned'
    terminal used by every other failure branch in this method."""
    ceremony = _make_ceremony()

    with (
        patch.object(ceremony, "_check_atomic_action_coverage", return_value=None),
        patch.object(ceremony, "_invoke_llm", new=AsyncMock(return_value="fixed")),
        patch.object(ceremony, "_pack_crate", new=AsyncMock(return_value="crate-1")),
        patch.object(ceremony, "_align_staged_file", new=AsyncMock(return_value=None)),
        patch.object(ceremony, "_run_canary", new=AsyncMock(return_value=True)),
        patch.object(ceremony, "_generate_patch", new=AsyncMock(return_value=None)),
        patch(
            "will.remediation.ceremony.submit_and_persist_fix", new=AsyncMock()
        ) as submit_mock,
    ):
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is False
    submit_mock.assert_not_called()
    ceremony._blackboard.mark_findings.assert_awaited_with(_FINDINGS, "abandoned")


@pytest.mark.asyncio
# ID: d3e99050-d9cd-40df-ac62-9179239bf9c1
async def test_execute_file_missing_rule_id_fails_without_generating_patch() -> None:
    """A finding with no resolvable rule id must stop the ceremony before
    patch generation or validation are ever attempted."""
    ceremony = _make_ceremony()
    findings = [{"id": "f1", "payload": {"file_path": "pkg/mod.py"}}]  # no "rule"

    with (
        patch.object(ceremony, "_check_atomic_action_coverage", return_value=None),
        patch.object(ceremony, "_invoke_llm", new=AsyncMock(return_value="fixed")),
        patch.object(ceremony, "_pack_crate", new=AsyncMock(return_value="crate-1")),
        patch.object(ceremony, "_align_staged_file", new=AsyncMock(return_value=None)),
        patch.object(ceremony, "_run_canary", new=AsyncMock(return_value=True)),
        patch.object(
            ceremony, "_generate_patch", new=AsyncMock(return_value="patch")
        ) as gen_patch,
        patch(
            "will.remediation.ceremony.submit_and_persist_fix", new=AsyncMock()
        ) as submit_mock,
    ):
        result = await ceremony._execute_file("pkg/mod.py", findings, _plan())

    assert result is False
    gen_patch.assert_not_called()
    submit_mock.assert_not_called()


@pytest.mark.asyncio
# ID: eebcbed9-272a-4b84-bcf7-47d50a7de1ae
async def test_execute_file_validate_diff_called_with_baseline_sha_and_rule_ids() -> (
    None
):
    """The persisted-validation call must thread plan.baseline_sha as
    base_sha and the deduplicated rule set as finding_rules via
    submit_and_persist_fix's params — the exact base-SHA invariant patch
    generation and validation must share, now flowing through the durable
    path rather than a raw ActionExecutor call."""
    ceremony = _make_ceremony()
    findings = [
        {"id": "f1", "payload": {"rule": "rule.b", "file_path": "pkg/mod.py"}},
        {"id": "f2", "payload": {"rule": "rule.a", "file_path": "pkg/mod.py"}},
    ]

    with (
        patch.object(ceremony, "_check_atomic_action_coverage", return_value=None),
        patch.object(ceremony, "_invoke_llm", new=AsyncMock(return_value="fixed")),
        patch.object(ceremony, "_pack_crate", new=AsyncMock(return_value="crate-1")),
        patch.object(ceremony, "_align_staged_file", new=AsyncMock(return_value=None)),
        patch.object(ceremony, "_run_canary", new=AsyncMock(return_value=True)),
        patch.object(
            ceremony, "_generate_patch", new=AsyncMock(return_value="patch-text")
        ),
        patch(
            "will.remediation.ceremony.submit_and_persist_fix",
            new=AsyncMock(return_value=("run-x", MagicMock(ok=False, data={}))),
        ) as submit_mock,
    ):
        await ceremony._execute_file("pkg/mod.py", findings, _plan())

    submit_mock.assert_awaited_once_with(
        context=ceremony._ctx,
        fix_id="assisted.validate_diff",
        write=True,
        params={
            "patch": "patch-text",
            "finding_rules": ["rule.a", "rule.b"],
            "subject_files": ["pkg/mod.py"],
            "base_sha": "base-sha",
        },
    )


# --- ADR-154 D3: canonical worker-backed ceremony -> human-gated PENDING ---


def _mk_candidate(**overrides):
    from datetime import UTC, datetime

    from shared.models.validated_remediation_candidate import (
        _CONSTRUCTOR_TOKEN,
        ValidatedRemediationCandidate,
    )

    defaults = dict(
        candidate_id="cand-1",
        patch="--- a/x\n+++ b/x\n",
        patch_digest="digest-1",
        production_set=["pkg/mod.py"],
        validated_base_sha="base-sha",
        validation_checks=["patch_applies"],
        validation_results={"patch_applies": True},
        finding_ids=["f1"],
        rule_ids=["rule.a"],
        created_at=datetime.now(UTC),
        _construction_token=_CONSTRUCTOR_TOKEN,
    )
    defaults.update(overrides)
    return ValidatedRemediationCandidate(**defaults)


def _enter_passing_mocks(
    stack: ExitStack, ceremony, validation_run_id: str = "run-1"
) -> None:
    """Enter the common patch set (everything up through a passing
    assisted.validate_diff) into *stack*."""
    stack.enter_context(
        patch.object(ceremony, "_check_atomic_action_coverage", return_value=None)
    )
    stack.enter_context(
        patch.object(ceremony, "_invoke_llm", new=AsyncMock(return_value="fixed"))
    )
    stack.enter_context(
        patch.object(ceremony, "_pack_crate", new=AsyncMock(return_value="crate-1"))
    )
    stack.enter_context(
        patch.object(ceremony, "_align_staged_file", new=AsyncMock(return_value=None))
    )
    stack.enter_context(
        patch.object(ceremony, "_run_canary", new=AsyncMock(return_value=True))
    )
    stack.enter_context(
        patch.object(
            ceremony,
            "_generate_patch",
            new=AsyncMock(return_value="--- a/x\n+++ b/x\n"),
        )
    )
    stack.enter_context(
        _patch_submit_and_persist_fix(ok=True, run_id=validation_run_id)
    )


@pytest.mark.asyncio
# ID: 16a4560c-0a5d-4bbf-9a7b-f943ec34c71a
async def test_execute_file_worker_backed_creates_draft() -> None:
    """A canonical worker-backed ceremony (real worker_uuid) with passing
    validation creates a PENDING via the atomic submission path and returns
    without ever applying or committing — that terminus no longer exists
    in this ceremony (ADR-154 D4)."""
    ceremony = _make_ceremony(worker_uuid=_WORKER_UUID)
    candidate = _mk_candidate()

    with ExitStack() as stack:
        _enter_passing_mocks(stack, ceremony)
        build_mock = stack.enter_context(
            patch(
                "will.remediation.ceremony.build_validated_candidate",
                new=AsyncMock(return_value=candidate),
            )
        )
        submit_mock = stack.enter_context(
            patch(
                "will.remediation.ceremony.submit_ceremony_proposal",
                new=AsyncMock(return_value="proposal-1"),
            )
        )
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is True
    build_mock.assert_awaited_once()
    assert build_mock.await_args.kwargs["finding_ids"] == ["f1"]
    assert build_mock.await_args.kwargs["rule_ids"] == ["rule.a"]
    assert build_mock.await_args.kwargs["subject_files"] == ["pkg/mod.py"]

    submit_mock.assert_awaited_once()
    assert submit_mock.await_args.kwargs["finding_ids"] == ["f1"]
    assert submit_mock.await_args.kwargs["expected_worker_uuid"] == _WORKER_UUID
    assert submit_mock.await_args.kwargs["expected_rule_ids"] == ["rule.a"]

    # Never applies or commits.
    ceremony._ctx.git_service.commit_paths.assert_not_called()
    ceremony._blackboard.post_observation.assert_not_called()
    ceremony._blackboard.mark_findings.assert_not_called()

    report_call = ceremony._blackboard.post_report.await_args
    assert report_call.kwargs["payload"]["proposal_id"] == "proposal-1"
    assert report_call.kwargs["payload"]["candidate_id"] == "cand-1"


@pytest.mark.asyncio
# ID: 8341f89a-c1f6-4b50-9684-251162c8976e
async def test_execute_file_candidate_construction_failure_aborts() -> None:
    from shared.models.validated_remediation_candidate import (
        CandidateConstructionError,
    )

    ceremony = _make_ceremony(worker_uuid=_WORKER_UUID)

    with ExitStack() as stack:
        _enter_passing_mocks(stack, ceremony)
        stack.enter_context(
            patch(
                "will.remediation.ceremony.build_validated_candidate",
                new=AsyncMock(side_effect=CandidateConstructionError("boom")),
            )
        )
        submit_mock = stack.enter_context(
            patch("will.remediation.ceremony.submit_ceremony_proposal", new=AsyncMock())
        )
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is False
    submit_mock.assert_not_called()
    post_failed_call = ceremony._blackboard.post_failed.await_args
    assert "Candidate construction failed" in post_failed_call.args[3]


@pytest.mark.asyncio
# ID: 08884b49-4fa2-4c1c-b502-bedb704aba91
async def test_execute_file_ceremony_submission_failure_does_not_touch_findings() -> (
    None
):
    """A failed atomic submission must not call mark_findings at all — the
    submission is all-or-nothing and changes nothing in the DB on failure,
    so there is nothing to release/abandon, and doing so unconditionally
    risks mutating a finding that now belongs to a different worker."""
    from body.services.proposal_submission_service import ProposalSubmissionError

    ceremony = _make_ceremony(worker_uuid=_WORKER_UUID)
    candidate = _mk_candidate()

    with ExitStack() as stack:
        _enter_passing_mocks(stack, ceremony)
        stack.enter_context(
            patch(
                "will.remediation.ceremony.build_validated_candidate",
                new=AsyncMock(return_value=candidate),
            )
        )
        stack.enter_context(
            patch(
                "will.remediation.ceremony.submit_ceremony_proposal",
                new=AsyncMock(side_effect=ProposalSubmissionError("stale claim")),
            )
        )
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is False
    ceremony._blackboard.mark_findings.assert_not_called()
    post_failed_call = ceremony._blackboard.post_failed.await_args
    assert "Ceremony proposal submission failed" in post_failed_call.args[3]


# --- ADR-154 D3a: file-mode is candidate-export-only — it must NEVER
# reach apply/commit. ---


@pytest.mark.asyncio
# ID: 94eb2d61-eda8-463a-8193-c3ce3d4658e2
async def test_execute_file_file_mode_is_candidate_export_only() -> None:
    """File-mode (no real worker identity) -> candidate produced, no
    proposal, no apply, no commit."""
    ceremony = _make_ceremony(worker_uuid=None)
    candidate = _mk_candidate()

    with ExitStack() as stack:
        _enter_passing_mocks(stack, ceremony)
        build_mock = stack.enter_context(
            patch(
                "will.remediation.ceremony.build_validated_candidate",
                new=AsyncMock(return_value=candidate),
            )
        )
        submit_mock = stack.enter_context(
            patch("will.remediation.ceremony.submit_ceremony_proposal", new=AsyncMock())
        )
        mock_svc = stack.enter_context(
            patch("body.services.crate_processing_service.CrateProcessingService")
        )
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is True
    build_mock.assert_awaited_once()
    assert build_mock.await_args.kwargs["finding_ids"] == ["f1"]
    submit_mock.assert_not_called()
    mock_svc.return_value.apply_and_finalize_crate.assert_not_called()
    ceremony._ctx.git_service.commit_paths.assert_not_called()
    obs_call = ceremony._blackboard.post_observation.await_args
    assert obs_call.kwargs["payload"]["candidate_id"] == "cand-1"


@pytest.mark.asyncio
# ID: b81d6676-7219-4f62-bad5-fa543314c147
async def test_export_candidate_only_candidate_construction_failure() -> None:
    from shared.models.validated_remediation_candidate import (
        CandidateConstructionError,
    )

    ceremony = _make_ceremony(worker_uuid=None)

    with ExitStack() as stack:
        _enter_passing_mocks(stack, ceremony)
        stack.enter_context(
            patch(
                "will.remediation.ceremony.build_validated_candidate",
                new=AsyncMock(side_effect=CandidateConstructionError("boom")),
            )
        )
        mock_svc = stack.enter_context(
            patch("body.services.crate_processing_service.CrateProcessingService")
        )
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is False
    mock_svc.return_value.apply_and_finalize_crate.assert_not_called()
    ceremony._ctx.git_service.commit_paths.assert_not_called()
    post_failed_call = ceremony._blackboard.post_failed.await_args
    assert "Candidate construction failed" in post_failed_call.args[3]


# ID: e6083694-5f6d-438f-b26c-6bf90f6f091f
async def test_process_file():
    core_context = MagicMock()
    blackboard = MagicMock()

    ceremony = RemediationCeremony(
        core_context=core_context,
        target_rule="some-rule",
        blackboard=blackboard,
    )

    ceremony._process_file = AsyncMock(return_value=True)

    findings = [{"id": "f1"}, {"id": "f2"}]
    result = await ceremony.process_file("src/example.py", findings)

    ceremony._process_file.assert_awaited_once_with("src/example.py", findings)
    assert result is True




# ID: caf36971-f3b3-4e63-bfa7-e82f465c6da0
def test_RemediationCeremony() -> None:
    from will.remediation.ceremony import RemediationCeremony

    core_context = MagicMock()
    target_rule = "some.rule"
    blackboard = MagicMock()

    with patch(
        "will.remediation.ceremony.RemediationInterpretationService",
        MagicMock(),
    ) as mock_interpretation_service_cls:
        ceremony = RemediationCeremony(
            core_context=core_context,
            target_rule=target_rule,
            blackboard=blackboard,
        )

    mock_interpretation_service_cls.assert_called_once_with()
    assert ceremony._ctx is core_context
    assert ceremony._target_rule == target_rule
    assert ceremony._blackboard is blackboard
    assert (
        ceremony._interpretation_service is mock_interpretation_service_cls.return_value
    )
