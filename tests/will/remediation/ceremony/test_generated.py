from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.remediation.ceremony import RemediationCeremony
from will.remediation.models import _RemediationPlan


def _make_ceremony(write: bool = False) -> RemediationCeremony:
    ctx = MagicMock()
    ctx.action_executor = AsyncMock()
    blackboard = AsyncMock()
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
    ceremony._ctx.action_executor.execute.return_value = MagicMock(
        ok=False, data={"error": "rule.a still fires"}
    )

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
    ):
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is False
    ceremony._ctx.git_service.commit_paths.assert_not_called()
    ceremony._blackboard.mark_findings.assert_awaited_with(_FINDINGS, "abandoned")
    post_failed_call = ceremony._blackboard.post_failed.await_args
    assert "assisted.validate_diff failed" in post_failed_call.args[4]


@pytest.mark.asyncio
async def test_execute_file_blocks_dry_run_on_failed_validation() -> None:
    """The gate applies to dry-run mode too — a failed verdict must not
    reach the dry-run observation post either."""
    ceremony = _make_ceremony(write=False)
    ceremony._ctx.action_executor.execute.return_value = MagicMock(
        ok=False, data={"error": "rule.a still fires"}
    )

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
    ):
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is False
    ceremony._ctx.action_executor.execute.assert_not_called()
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
    ):
        result = await ceremony._execute_file("pkg/mod.py", findings, _plan())

    assert result is False
    gen_patch.assert_not_called()
    ceremony._ctx.action_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_execute_file_write_mode_proceeds_after_passing_validation() -> None:
    """The passing case must be unchanged: a clean assisted.validate_diff
    verdict lets the legacy write branch run exactly as before."""
    ceremony = _make_ceremony(write=True)
    ceremony._ctx.action_executor.execute.return_value = MagicMock(
        ok=True, data={"validation_results": {"audit_rule_cleared:rule.a": True}}
    )

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
        patch(
            "body.services.crate_processing_service.CrateProcessingService"
        ) as mock_svc,
    ):
        mock_svc.return_value.apply_and_finalize_crate = AsyncMock(return_value=None)
        result = await ceremony._execute_file("pkg/mod.py", _FINDINGS, _plan())

    assert result is True
    mock_svc.return_value.apply_and_finalize_crate.assert_awaited_once_with("crate-1")
    ceremony._ctx.git_service.commit_paths.assert_called_once()
    ceremony._blackboard.mark_findings.assert_awaited_with(_FINDINGS, "resolved")


@pytest.mark.asyncio
async def test_execute_file_validate_diff_called_with_baseline_sha_and_rule_ids() -> (
    None
):
    """The validation call must thread plan.baseline_sha as base_sha and the
    deduplicated rule set as finding_rules — the exact base-SHA invariant
    patch generation and validation must share."""
    ceremony = _make_ceremony(write=False)
    ceremony._ctx.action_executor.execute.return_value = MagicMock(
        ok=False, data={"error": "x"}
    )
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
    ):
        await ceremony._execute_file("pkg/mod.py", findings, _plan())

    ceremony._ctx.action_executor.execute.assert_awaited_once_with(
        "assisted.validate_diff",
        write=True,
        patch="patch-text",
        finding_rules=["rule.a", "rule.b"],
        subject_files=["pkg/mod.py"],
        base_sha="base-sha",
    )
