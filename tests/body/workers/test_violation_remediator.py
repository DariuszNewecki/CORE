# tests/body/workers/test_violation_remediator.py
"""
Tests for ViolationRemediator — new failure paths introduced in v2.

Covers:
  1. Brief build failure        → findings marked 'indeterminate', execution halted
  2. Low role confidence (write) → findings marked 'indeterminate', execution halted
  3. Git commit failure          → findings marked 'abandoned' (NOT 'resolved')

Each test is self-contained. All DB, filesystem, and service calls are mocked
at the boundary so no real infrastructure is required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.workers.violation_remediator import (
    ViolationRemediator,
)
from will.self_healing.remediation_interpretation.service import (
    RemediationInterpretationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RULE_ID = "architecture.max_file_size"
_FILE_PATH = "src/will/self_healing/some_service.py"
_SOURCE_CODE = "def placeholder(): pass\n"

_FINDING = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "subject": f"audit.violation::{_RULE_ID}::{_FILE_PATH}",
    "payload": {
        "file_path": _FILE_PATH,
        "rule": _RULE_ID,
        "severity": "error",
        "message": "File exceeds 400 lines.",
        "line_number": None,
    },
}

_ARCHITECTURAL_CONTEXT_HIGH_CONFIDENCE = {
    "file_path": _FILE_PATH,
    "file_role": {
        "role_id": "service",
        "layer": "will",
        "confidence": 0.92,
        "evidence": ["Path indicates service."],
    },
    "findings": [],
    "responsibility_clusters": [],
    "candidate_strategies": [],
    "recommended_strategy": None,
    "constraints": [],
    "architectural_notes": [],
}

_ARCHITECTURAL_CONTEXT_LOW_CONFIDENCE = {
    **_ARCHITECTURAL_CONTEXT_HIGH_CONFIDENCE,
    "file_role": {
        "role_id": "unknown",
        "layer": "unknown",
        "confidence": 0.30,  # below _MIN_ROLE_CONFIDENCE_FOR_WRITE
        "evidence": ["No strong signal from path."],
    },
}


def _make_core_context(*, repo_file_exists: bool = True) -> MagicMock:
    """Build a minimal CoreContext mock sufficient for _plan_file."""
    ctx = MagicMock()

    # git_service — repo_path must be a MagicMock (not a real Path) so that
    # __truediv__ (the / operator used in the worker) is patchable.
    fake_path = MagicMock(spec=Path)
    if repo_file_exists:
        fake_path.read_text.return_value = _SOURCE_CODE
    else:
        fake_path.read_text.side_effect = OSError("file not found")

    repo_path_mock = MagicMock(spec=Path)
    repo_path_mock.__truediv__ = MagicMock(return_value=fake_path)
    ctx.git_service.repo_path = repo_path_mock
    ctx.git_service.get_current_commit.return_value = "abc1234"

    # file_handler (for rollback archive)
    ctx.file_handler = MagicMock()
    ctx.file_handler.ensure_dir = MagicMock()
    ctx.file_handler.write_runtime_json = MagicMock()

    return ctx


def _make_worker(
    *,
    write: bool = False,
    core_context: MagicMock | None = None,
) -> ViolationRemediator:
    ctx = core_context or _make_core_context()
    worker = ViolationRemediator(
        core_context=ctx,
        target_rule=_RULE_ID,
        write=write,
    )
    return worker


# ---------------------------------------------------------------------------
# Test 1 — brief build failure → indeterminate, execution halted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brief_build_failure_marks_indeterminate_and_halts() -> None:
    """
    When RemediationInterpretationService raises RemediationInterpretationError,
    _plan_file must:
      - mark findings 'indeterminate'
      - post a failure finding
      - return None (halting the ceremony)

    The LLM must never be invoked.
    """
    worker = _make_worker(write=True)

    # Service raises on this file
    worker._interpretation_service = MagicMock()
    worker._interpretation_service.build_reasoning_brief_dict.side_effect = (
        RemediationInterpretationError("AST parse failed")
    )

    marked_statuses: list[str] = []

    async def fake_mark_findings(findings: list, status: str) -> None:
        marked_statuses.append(status)

    worker._mark_findings = fake_mark_findings
    worker._post_failed = AsyncMock()

    # _execute_file must not run — track calls via _invoke_llm
    worker._invoke_llm = AsyncMock()

    result = await worker._process_file(_FILE_PATH, [_FINDING])

    assert result is False, "Expected False when planning is indeterminate"
    assert (
        "indeterminate" in marked_statuses
    ), f"Expected 'indeterminate' in status updates, got: {marked_statuses}"
    assert (
        "resolved" not in marked_statuses
    ), "Findings must not be marked 'resolved' after an indeterminate outcome"
    worker._invoke_llm.assert_not_awaited(), (
        "LLM must not be invoked when planning is indeterminate"
    )
    worker._post_failed.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 2 — low role confidence in write mode → indeterminate, execution halted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_confidence_in_write_mode_marks_indeterminate_and_halts() -> None:
    """
    When architectural context returns role confidence below
    _MIN_ROLE_CONFIDENCE_FOR_WRITE and write=True, _plan_file must:
      - mark findings 'indeterminate'
      - post a failure finding
      - return None

    The same file in dry-run mode must proceed (confidence gate is write-only).
    """
    # --- write mode: should block ---
    worker_write = _make_worker(write=True)
    worker_write._interpretation_service = MagicMock()
    worker_write._interpretation_service.build_reasoning_brief_dict.return_value = (
        _ARCHITECTURAL_CONTEXT_LOW_CONFIDENCE
    )

    marked_write: list[str] = []

    async def fake_mark_write(findings: list, status: str) -> None:
        marked_write.append(status)

    worker_write._mark_findings = fake_mark_write
    worker_write._post_failed = AsyncMock()
    worker_write._invoke_llm = AsyncMock()

    result_write = await worker_write._process_file(_FILE_PATH, [_FINDING])

    assert (
        result_write is False
    ), "Expected False: low confidence should block write-mode execution"
    assert (
        "indeterminate" in marked_write
    ), f"Expected 'indeterminate', got: {marked_write}"
    worker_write._invoke_llm.assert_not_awaited()

    # --- dry-run mode: should proceed past confidence gate ---
    worker_dry = _make_worker(write=False)
    worker_dry._interpretation_service = MagicMock()
    worker_dry._interpretation_service.build_reasoning_brief_dict.return_value = (
        _ARCHITECTURAL_CONTEXT_LOW_CONFIDENCE
    )

    # Stub out the rest of the ceremony so the test stays focused
    worker_dry._mark_findings = AsyncMock()
    worker_dry._post_failed = AsyncMock()
    worker_dry._build_context = AsyncMock(return_value="")
    worker_dry._invoke_llm = AsyncMock(
        return_value=None
    )  # LLM returns nothing → abandoned

    result_dry = await worker_dry._process_file(_FILE_PATH, [_FINDING])

    # Dry-run reached _invoke_llm — the confidence gate did not block it
    worker_dry._invoke_llm.assert_awaited_once()
    # Result may be False (LLM returned None), but the gate was passed
    assert "indeterminate" not in [
        call.args[1] for call in worker_dry._mark_findings.await_args_list
    ], "Confidence gate must not fire in dry-run mode"


# ---------------------------------------------------------------------------
# Test 3 — git commit failure → abandoned, NOT resolved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_git_commit_failure_marks_abandoned_not_resolved() -> None:
    """
    When the git commit fails after a successful apply, _execute_file must:
      - mark findings 'abandoned'
      - NOT mark findings 'resolved'
      - post a failure finding describing the uncommitted state
      - return False

    This prevents the blackboard and the repo from disagreeing about
    whether the fix is live.
    """
    ctx = _make_core_context()

    # Commit raises after apply succeeds
    ctx.git_service.commit.side_effect = RuntimeError("lock file exists")

    worker = _make_worker(write=True, core_context=ctx)

    # Planning succeeds with high-confidence context
    worker._interpretation_service = MagicMock()
    worker._interpretation_service.build_reasoning_brief_dict.return_value = (
        _ARCHITECTURAL_CONTEXT_HIGH_CONFIDENCE
    )

    # LLM returns a valid fix
    worker._invoke_llm = AsyncMock(return_value=_SOURCE_CODE)
    worker._build_context = AsyncMock(return_value="")

    # Crate + canary pass
    worker._pack_crate = AsyncMock(return_value="crate-uuid-001")
    worker._run_canary = AsyncMock(return_value=True)

    # Apply succeeds
    mock_crate_service = MagicMock()
    mock_crate_service.apply_and_finalize_crate = AsyncMock()

    marked_statuses: list[str] = []

    async def fake_mark_findings(findings: list, status: str) -> None:
        marked_statuses.append(status)

    worker._mark_findings = fake_mark_findings
    worker.post_finding = AsyncMock()
    worker._post_failed = AsyncMock()

    # CrateProcessingService is imported inside _execute_file via a local
    # 'from body.services.crate_processing_service import ...' — patch it
    # at the source module, not at the worker module.
    with patch(
        "body.services.crate_processing_service.CrateProcessingService",
        return_value=mock_crate_service,
    ):
        result = await worker._process_file(_FILE_PATH, [_FINDING])

    assert result is False, "Expected False: git commit failure must not return success"
    assert (
        "abandoned" in marked_statuses
    ), f"Expected 'abandoned' in status updates, got: {marked_statuses}"
    assert "resolved" not in marked_statuses, (
        "Findings must NOT be marked 'resolved' when the git commit failed. "
        "The fix is applied to disk but not committed — blackboard integrity requires 'abandoned'."
    )
    worker._post_failed.assert_awaited_once()

    # Failure message must mention uncommitted state
    failure_reason: str = worker._post_failed.call_args.args[2]
    assert (
        "uncommitted" in failure_reason.lower() or "commit" in failure_reason.lower()
    ), f"Failure reason must describe the uncommitted state, got: {failure_reason!r}"
