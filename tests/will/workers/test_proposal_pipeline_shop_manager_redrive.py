"""Tests for ProposalPipelineShopManager._redrive_undeferred_findings
(ADR-148-adjacent, #764 — creation-side outbox).

No real DB required — service_registry is mocked. Sibling to
test_proposal_pipeline_shop_manager_retire.py and
test_proposal_pipeline_shop_manager_roll_forward.py.

Invariants:
  1. deferred_count > 0 -> True
  2. deferred_count == 0 (nothing left to defer, e.g. a concurrent redrive
     already caught it) -> False
  3. no finding_ids on the row -> short-circuits, service never called
  4. DB error -> swallowed (fail-soft) -> False
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.proposal_pipeline_shop_manager import _SUBJECT_STUCK_UNDEFERRED


def test_stuck_undeferred_subject_prefix_value() -> None:
    """Resolver-ownership backing (ADR-091 D2 Rev B (d)) for the
    proposal.stuck_undeferred self_resolve subject (#764) — same gap #778
    found for stuck_finalizing: the module docstring documents the
    resolver path, but a test must also reference the subject prefix
    literal.
    """
    assert _SUBJECT_STUCK_UNDEFERRED == "proposal.stuck_undeferred"


def _make_worker_instance() -> object:
    """Bypass Worker.__init__ (reads .intent/) — set minimal attributes by hand."""
    from will.workers.proposal_pipeline_shop_manager import ProposalPipelineShopManager

    w = object.__new__(ProposalPipelineShopManager)
    w._declaration = {}
    w._max_interval = 300
    return w


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "proposal_id": "pid-undeferred-1",
        "finding_ids": ["fid-a", "fid-b"],
        "seconds_stuck": 300,
    }
    base.update(overrides)
    return base


async def test_redrive_returns_true_when_findings_deferred() -> None:
    """A successful redrive that deferred at least one finding returns True."""
    worker = _make_worker_instance()
    blackboard_svc = AsyncMock()
    blackboard_svc.defer_entries_to_proposal = AsyncMock(return_value=2)

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)

    with patch(
        "body.services.service_registry.service_registry", mock_registry
    ):
        result = await worker._redrive_undeferred_findings(_row())  # type: ignore[attr-defined]

    assert result is True
    blackboard_svc.defer_entries_to_proposal.assert_awaited_once_with(
        ["fid-a", "fid-b"], "pid-undeferred-1"
    )


async def test_redrive_returns_false_when_nothing_deferred() -> None:
    """defer_entries_to_proposal returning 0 (e.g. a concurrent redrive
    already caught it, or a status-guard mismatch) returns False."""
    worker = _make_worker_instance()
    blackboard_svc = AsyncMock()
    blackboard_svc.defer_entries_to_proposal = AsyncMock(return_value=0)

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)

    with patch(
        "body.services.service_registry.service_registry", mock_registry
    ):
        result = await worker._redrive_undeferred_findings(_row())  # type: ignore[attr-defined]

    assert result is False


async def test_redrive_short_circuits_with_no_finding_ids() -> None:
    """A row with no finding_ids never calls the blackboard service."""
    worker = _make_worker_instance()
    blackboard_svc = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)

    with patch(
        "body.services.service_registry.service_registry", mock_registry
    ):
        result = await worker._redrive_undeferred_findings(  # type: ignore[attr-defined]
            _row(finding_ids=[])
        )

    assert result is False
    blackboard_svc.defer_entries_to_proposal.assert_not_awaited()


async def test_redrive_fail_soft_on_db_error() -> None:
    """A DB error during the redrive is caught and swallowed; the method
    returns False without propagating the exception."""
    worker = _make_worker_instance()
    blackboard_svc = AsyncMock()
    blackboard_svc.defer_entries_to_proposal = AsyncMock(
        side_effect=RuntimeError("db down")
    )

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)

    with patch(
        "body.services.service_registry.service_registry", mock_registry
    ):
        result = await worker._redrive_undeferred_findings(_row())  # type: ignore[attr-defined]

    assert result is False
