"""
Unit tests for ProposalPipelineShopManager._roll_forward_finalizing.

Verifies the stuck-finalizing roll-forward path (ADR-148 D4) — no real DB
required; service_registry and pipeline steps are mocked. Sibling to
test_proposal_pipeline_shop_manager_retire.py (stuck_executing path).

Also closes the ADR-091 D2 Revision B (d) resolver-ownership test gap for
the `proposal.stuck_finalizing` self_resolve subject prefix (#778): the
module docstring documents the resolver path, but no test referenced the
subject prefix until this file.

Invariants:
  1. no consequence record  -> records one -> resolves findings -> completes -> True
  2. consequence already recorded -> skips record_consequence -> completes -> True
  3. record_consequence fails -> mark_completed NOT called -> False
  4. resolve_deferred_findings fails -> mark_completed NOT called -> False
  5. ProposalNotFoundError from mark_completed (concurrent completion) -> False
  6. unexpected exception -> swallowed (fail-soft) -> False
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.proposal_pipeline_shop_manager import _SUBJECT_STUCK_FINALIZING


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_stuck_finalizing_subject_prefix_value() -> None:
    """Resolver-ownership backing (ADR-091 D2 Rev B (d)) for the
    proposal.stuck_finalizing self_resolve subject — this is the test
    condition (2) that #778 found missing; the run() loop builds the
    posted finding's subject as f"{_SUBJECT_STUCK_FINALIZING}::<proposal_id>".
    """
    assert _SUBJECT_STUCK_FINALIZING == "proposal.stuck_finalizing"


@asynccontextmanager
async def _session_ctx(session: MagicMock):  # type: ignore[no-untyped-def]
    yield session


def _make_worker_instance() -> object:
    """Bypass Worker.__init__ (reads .intent/) — set minimal attributes by hand."""
    from will.workers.proposal_pipeline_shop_manager import ProposalPipelineShopManager

    w = object.__new__(ProposalPipelineShopManager)
    w._declaration = {}
    w._max_interval = 300
    return w


def _patch_service_registry(session: MagicMock):  # type: ignore[no-untyped-def]
    """
    Return (mock_svc, orig, svc_mod) — replace
    body.services.service_registry.service_registry with a mock whose
    .session() context manager yields the given session.

    Callers are responsible for restoring orig in a finally block.
    """
    import body.services.service_registry as svc_mod

    orig = svc_mod.service_registry
    mock_svc = MagicMock()
    mock_svc.session = MagicMock(return_value=_session_ctx(session))
    svc_mod.service_registry = mock_svc
    return mock_svc, orig, svc_mod


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "proposal_id": "pid-finalizing",
        "has_consequence": False,
        "execution_results": {},
        "finding_ids": [],
        "policies": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_roll_forward_records_consequence_resolves_and_completes() -> None:
    """No consequence record yet: records one, resolves deferred findings,
    marks completed, returns True."""
    worker = _make_worker_instance()
    session = AsyncMock()
    mark_completed_mock = AsyncMock()

    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with (
            patch(
                "will.autonomy.proposal_execution_pipeline.record_consequence",
                AsyncMock(return_value=True),
            ) as record_mock,
            patch(
                "will.autonomy.proposal_execution_pipeline.resolve_deferred_findings",
                AsyncMock(return_value=True),
            ) as resolve_mock,
            patch(
                "will.autonomy.proposal_state_manager.ProposalStateManager.mark_completed",
                mark_completed_mock,
            ),
        ):
            result = await worker._roll_forward_finalizing(  # type: ignore[attr-defined]
                _row()
            )
    finally:
        svc_mod.service_registry = orig

    assert result is True
    record_mock.assert_awaited_once()
    resolve_mock.assert_awaited_once_with("pid-finalizing")
    mark_completed_mock.assert_awaited_once_with("pid-finalizing")


async def test_roll_forward_skips_consequence_when_already_recorded() -> None:
    """has_consequence=True: record_consequence is NOT called; still
    resolves findings and completes."""
    worker = _make_worker_instance()
    session = AsyncMock()
    mark_completed_mock = AsyncMock()

    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with (
            patch(
                "will.autonomy.proposal_execution_pipeline.record_consequence",
                AsyncMock(return_value=True),
            ) as record_mock,
            patch(
                "will.autonomy.proposal_execution_pipeline.resolve_deferred_findings",
                AsyncMock(return_value=True),
            ) as resolve_mock,
            patch(
                "will.autonomy.proposal_state_manager.ProposalStateManager.mark_completed",
                mark_completed_mock,
            ),
        ):
            result = await worker._roll_forward_finalizing(  # type: ignore[attr-defined]
                _row(has_consequence=True)
            )
    finally:
        svc_mod.service_registry = orig

    assert result is True
    record_mock.assert_not_awaited()
    resolve_mock.assert_awaited_once_with("pid-finalizing")
    mark_completed_mock.assert_awaited_once_with("pid-finalizing")


async def test_roll_forward_returns_false_when_record_consequence_fails() -> None:
    """record_consequence returning False leaves the proposal finalizing —
    mark_completed must not be reached."""
    worker = _make_worker_instance()
    session = AsyncMock()
    mark_completed_mock = AsyncMock()

    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with (
            patch(
                "will.autonomy.proposal_execution_pipeline.record_consequence",
                AsyncMock(return_value=False),
            ),
            patch(
                "will.autonomy.proposal_execution_pipeline.resolve_deferred_findings",
                AsyncMock(return_value=True),
            ) as resolve_mock,
            patch(
                "will.autonomy.proposal_state_manager.ProposalStateManager.mark_completed",
                mark_completed_mock,
            ),
        ):
            result = await worker._roll_forward_finalizing(  # type: ignore[attr-defined]
                _row()
            )
    finally:
        svc_mod.service_registry = orig

    assert result is False
    resolve_mock.assert_not_awaited()
    mark_completed_mock.assert_not_awaited()


async def test_roll_forward_returns_false_when_resolve_findings_fails() -> None:
    """resolve_deferred_findings returning False leaves the proposal
    finalizing — mark_completed must not be reached."""
    worker = _make_worker_instance()
    session = AsyncMock()
    mark_completed_mock = AsyncMock()

    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with (
            patch(
                "will.autonomy.proposal_execution_pipeline.record_consequence",
                AsyncMock(return_value=True),
            ),
            patch(
                "will.autonomy.proposal_execution_pipeline.resolve_deferred_findings",
                AsyncMock(return_value=False),
            ),
            patch(
                "will.autonomy.proposal_state_manager.ProposalStateManager.mark_completed",
                mark_completed_mock,
            ),
        ):
            result = await worker._roll_forward_finalizing(  # type: ignore[attr-defined]
                _row(has_consequence=True)
            )
    finally:
        svc_mod.service_registry = orig

    assert result is False
    mark_completed_mock.assert_not_awaited()


async def test_roll_forward_concurrent_completion_is_safe_no_op() -> None:
    """mark_completed raising ProposalNotFoundError (already completed by
    ProposalConsumerWorker) is caught — returns False without propagating."""
    from will.autonomy.proposal_state_manager import ProposalNotFoundError

    worker = _make_worker_instance()
    session = AsyncMock()
    mark_completed_mock = AsyncMock(
        side_effect=ProposalNotFoundError("pid-finalizing")
    )

    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with (
            patch(
                "will.autonomy.proposal_execution_pipeline.record_consequence",
                AsyncMock(return_value=True),
            ),
            patch(
                "will.autonomy.proposal_execution_pipeline.resolve_deferred_findings",
                AsyncMock(return_value=True),
            ),
            patch(
                "will.autonomy.proposal_state_manager.ProposalStateManager.mark_completed",
                mark_completed_mock,
            ),
        ):
            result = await worker._roll_forward_finalizing(  # type: ignore[attr-defined]
                _row(has_consequence=True)
            )
    finally:
        svc_mod.service_registry = orig

    assert result is False


async def test_roll_forward_fail_soft_on_unexpected_exception() -> None:
    """An unexpected exception anywhere in the pipeline is caught and
    swallowed — returns False without propagating."""
    worker = _make_worker_instance()
    session = AsyncMock()

    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with patch(
            "will.autonomy.proposal_execution_pipeline.record_consequence",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            result = await worker._roll_forward_finalizing(  # type: ignore[attr-defined]
                _row()
            )
    finally:
        svc_mod.service_registry = orig

    assert result is False
