from __future__ import annotations

import uuid
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.remediation.ceremony import RemediationCeremony
from will.remediation.models import _RemediationPlan


_WORKER_UUID = uuid.uuid4()


def _make_ceremony(
    write: bool = False, worker_uuid: uuid.UUID | None = None
) -> RemediationCeremony:
    """worker_uuid defaults to None (ADR-154 D3a shape: no real worker
    identity) so every pre-D3 test in this file keeps exercising the legacy
    dry-run/write branches it was written against, unchanged. D3-specific
    tests pass worker_uuid=_WORKER_UUID explicitly to reach
    _create_ceremony_draft instead."""
    ctx = MagicMock()
    ctx.action_executor = AsyncMock()
    blackboard = AsyncMock()
    blackboard.worker_uuid = worker_uuid
    return RemediationCeremony(
        core_context=ctx,
        target_rule="rule.a",
        write=write,
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


def test_collect_rule_ids_dedupes_and_sorts() -> None:
    ceremony = _make_ceremony()
    findings = [
        {"payload": {"rule": "rule.b"}},
        {"payload": {"rule": "rule.a"}},
        {"payload": {"rule": "rule.a"}},
    ]
    assert ceremony._collect_rule_ids(findings) == ["rule.a", "rule.b"]


def test_collect_rule_ids_none_on_missing_rule() -> None:
    """A finding with no resolvable rule must fail the collection entirely —
    never silently substitute 'unknown' into a set assisted.validate_diff
    will actually check."""
    ceremony = _make_ceremony()
    findings = [{"payload": {"rule": "rule.a"}}, {"payload": {}}]
    assert ceremony._collect_rule_ids(findings) is None


# --- _execute_file fail-closed gate (ADR-154 D1) ---


@pytest.mark.asyncio
async def test_execute_file_blocks_write_on_failed_validation() -> None:
    """Canary passes, assisted.validate_diff fails -> the legacy write branch
    (apply_and_finalize_crate / commit_paths) must never run. A failed gate
    cannot be silently bypassed by the not-yet-retired write path."""
    ceremony = _make_ceremony(write=True)

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
    ceremony._blackboard.mark_findings.assert_awaited_with(_FINDINGS, "abandoned")
    post_failed_call = ceremony._blackboard.post_failed.await_args
    assert "assisted.validate_diff failed" in post_failed_call.args[4]
    assert "run-123" in post_failed_call.args[4]


@pytest.mark.asyncio
async def test_execute_file_blocks_dry_run_on_failed_validation() -> None:
    """The gate applies to dry-run mode too — a failed verdict must not
    reach the dry-run observation post either."""
    ceremony = _make_ceremony(write=False)

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
    ceremony._blackboard.post_observation.assert_not_called()
    ceremony._blackboard.mark_findings.assert_awaited_with(_FINDINGS, "abandoned")


@pytest.mark.asyncio
async def test_execute_file_empty_patch_fails_without_calling_validate_diff() -> None:
    """No-op candidate (empty/unavailable diff) is its own precondition
    failure — it must never reach assisted.validate_diff at all, and must
    not invent a new finding disposition beyond the existing 'abandoned'
    terminal used by every other failure branch in this method."""
    ceremony = _make_ceremony(write=True)

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
async def test_execute_file_missing_rule_id_fails_without_generating_patch() -> None:
    """A finding with no resolvable rule id must stop the ceremony before
    patch generation or validation are ever attempted."""
    ceremony = _make_ceremony(write=True)
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
async def test_legacy_dry_run_and_write_write_mode_still_functions_in_isolation() -> (
    None
):
    """_legacy_dry_run_and_write is dead code as of the ADR-154 D3a
    correction — _execute_file no longer calls it for any caller (see
    test_legacy_dry_run_and_write_is_never_called_from_execute_file). It is
    kept defined, not deleted, for D4 to remove structurally; this test
    exercises it directly (bypassing _execute_file) to prove it still
    behaves correctly while it sits unreachable, so it doesn't silently
    rot before D4."""
    ceremony = _make_ceremony(write=True)

    with (
        patch(
            "body.services.crate_processing_service.CrateProcessingService"
        ) as mock_svc,
    ):
        mock_svc.return_value.apply_and_finalize_crate = AsyncMock(return_value=None)
        result = await ceremony._legacy_dry_run_and_write(
            "pkg/mod.py", _FINDINGS, _plan(), "crate-1", True, "fixed"
        )

    assert result is True
    mock_svc.return_value.apply_and_finalize_crate.assert_awaited_once_with("crate-1")
    ceremony._ctx.git_service.commit_paths.assert_called_once()
    ceremony._blackboard.mark_findings.assert_awaited_with(_FINDINGS, "resolved")


@pytest.mark.asyncio
async def test_legacy_dry_run_and_write_dry_run_mode_still_functions_in_isolation() -> (
    None
):
    """Same as above for the dry-run branch of the orphaned method."""
    ceremony = _make_ceremony(write=False)

    result = await ceremony._legacy_dry_run_and_write(
        "pkg/mod.py", _FINDINGS, _plan(), "crate-1", True, "fixed"
    )

    assert result is True
    obs_call = ceremony._blackboard.post_observation.await_args
    assert obs_call.kwargs["payload"]["proposed_fix"] == "fixed"
    ceremony._blackboard.mark_findings.assert_awaited_with(_FINDINGS, "abandoned")


@pytest.mark.asyncio
async def test_execute_file_validate_diff_called_with_baseline_sha_and_rule_ids() -> (
    None
):
    """The persisted-validation call must thread plan.baseline_sha as
    base_sha and the deduplicated rule set as finding_rules via
    submit_and_persist_fix's params — the exact base-SHA invariant patch
    generation and validation must share, now flowing through the durable
    path rather than a raw ActionExecutor call."""
    ceremony = _make_ceremony(write=False)
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


# --- ADR-154 D3: canonical worker-backed ceremony -> human-gated DRAFT ---


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
async def test_execute_file_worker_backed_creates_draft_and_skips_legacy_paths() -> (
    None
):
    """A canonical worker-backed ceremony (real worker_uuid) with passing
    validation creates a DRAFT via the atomic submission path and returns
    without ever reaching the legacy dry-run or write/apply/commit
    branches — regardless of self._write."""
    ceremony = _make_ceremony(write=True, worker_uuid=_WORKER_UUID)
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

    # Never reaches the legacy write/dry-run terminus.
    ceremony._ctx.git_service.commit_paths.assert_not_called()
    ceremony._blackboard.post_observation.assert_not_called()
    ceremony._blackboard.mark_findings.assert_not_called()

    report_call = ceremony._blackboard.post_report.await_args
    assert report_call.kwargs["payload"]["proposal_id"] == "proposal-1"
    assert report_call.kwargs["payload"]["candidate_id"] == "cand-1"


@pytest.mark.asyncio
async def test_execute_file_worker_backed_dry_run_also_creates_draft() -> None:
    """Proposal creation must not depend on the legacy write flag — a
    dry-run-mode ceremony with a real worker identity still creates a
    DRAFT, not the discovery-only dry-run observation."""
    ceremony = _make_ceremony(write=False, worker_uuid=_WORKER_UUID)
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
                new=AsyncMock(return_value="proposal-2"),
            )
        )
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is True
    ceremony._blackboard.post_observation.assert_not_called()


@pytest.mark.asyncio
async def test_execute_file_candidate_construction_failure_aborts() -> None:
    from shared.models.validated_remediation_candidate import (
        CandidateConstructionError,
    )

    ceremony = _make_ceremony(write=True, worker_uuid=_WORKER_UUID)

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
    assert "Candidate construction failed" in post_failed_call.args[4]


@pytest.mark.asyncio
async def test_execute_file_ceremony_submission_failure_does_not_touch_findings() -> (
    None
):
    """A failed atomic submission must not call mark_findings at all — the
    submission is all-or-nothing and changes nothing in the DB on failure,
    so there is nothing to release/abandon, and doing so unconditionally
    risks mutating a finding that now belongs to a different worker."""
    from body.services.proposal_submission_service import ProposalSubmissionError

    ceremony = _make_ceremony(write=True, worker_uuid=_WORKER_UUID)
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
    assert "Ceremony proposal submission failed" in post_failed_call.args[4]


# --- ADR-154 D3a correction (governor, 2026-08-23): file-mode is
# candidate-export-only — it must NEVER reach apply/commit, regardless of
# self._write. An earlier version of this file wrongly asserted the
# opposite (worker_uuid=None fell through to the legacy write branch);
# these tests replace that assertion with the corrected requirement. ---


@pytest.mark.asyncio
async def test_execute_file_file_mode_write_false_is_candidate_export_only() -> None:
    """1. file-mode + write=False -> candidate produced, no proposal, no
    apply, no commit."""
    ceremony = _make_ceremony(write=False, worker_uuid=None)
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
async def test_execute_file_file_mode_write_true_is_still_candidate_export_only() -> (
    None
):
    """2. file-mode + write=True -> SAME candidate-only behavior, no
    proposal, no apply, no commit. This is the exact defect the governor
    caught: worker_uuid=None must not depend on self._write at all."""
    ceremony = _make_ceremony(write=True, worker_uuid=None)
    candidate = _mk_candidate()

    with ExitStack() as stack:
        _enter_passing_mocks(stack, ceremony)
        stack.enter_context(
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
    submit_mock.assert_not_called()
    mock_svc.return_value.apply_and_finalize_crate.assert_not_called()
    ceremony._ctx.git_service.commit_paths.assert_not_called()


@pytest.mark.asyncio
async def test_export_candidate_only_candidate_construction_failure() -> None:
    from shared.models.validated_remediation_candidate import (
        CandidateConstructionError,
    )

    ceremony = _make_ceremony(write=True, worker_uuid=None)

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
    assert "Candidate construction failed" in post_failed_call.args[4]


@pytest.mark.asyncio
async def test_legacy_dry_run_and_write_is_never_called_from_execute_file() -> None:
    """Structural proof: _legacy_dry_run_and_write (the relocated dead
    code, kept physically present for D4) is not reachable from
    _execute_file for either worker-backed or file-mode ceremonies."""
    for worker_uuid, expect_proposal in ((_WORKER_UUID, True), (None, False)):
        ceremony = _make_ceremony(write=True, worker_uuid=worker_uuid)
        candidate = _mk_candidate()

        with ExitStack() as stack:
            _enter_passing_mocks(stack, ceremony)
            stack.enter_context(
                patch(
                    "will.remediation.ceremony.build_validated_candidate",
                    new=AsyncMock(return_value=candidate),
                )
            )
            if expect_proposal:
                stack.enter_context(
                    patch(
                        "will.remediation.ceremony.submit_ceremony_proposal",
                        new=AsyncMock(return_value="proposal-x"),
                    )
                )
            legacy_mock = stack.enter_context(
                patch.object(ceremony, "_legacy_dry_run_and_write", new=AsyncMock())
            )
            await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

        legacy_mock.assert_not_called()
