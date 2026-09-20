# tests/will/workers/test_proposal_pipeline_shop_manager_stuck_deferred_terminal.py
"""ProposalPipelineShopManager's fifth pass: findings deferred to a proposal
that already ended are routed to where the proposal's own terminating actor
would have put them (G4 P2 pre-condition; terminate-side twin of #764/#886).

Live evidence, 2026-09-20: 48 findings in ``deferred_to_proposal`` on
terminal proposals (37 rejected, 10 failed, 1 completed; May-July), 6 of
them still-live ``style.formatter_required`` violations stranded since a
proposal failed on 07-26 — the sensor dedups against ``deferred_to_proposal``,
so they were never re-posted and never remediated. Every existing revival
is executed by the actor that terminates the proposal, in the same cycle;
if that actor dies first, nothing reconciles.

Pinned here:
- the routing table of ``_reconcile_stuck_deferred_terminal`` — one
  destination per terminal state, each an existing predicate, none new:
  failed/missing → ``revive_and_report`` (ADR-104 D9 cap, lineage-aware);
  rejected → the governor inbox, ``indeterminate`` + ``human``, NEVER back
  to the remediator (a stranded rejection runs with no human present and
  no recorded reason — re-proposing is the only outcome that can
  contradict a decision on record; ADR-104 D10 applied); completed with a
  real commit → ``resolve_deferred_findings``; completed no-op →
  ``revive_deferred_findings_for_noop`` (ADR-104 D10);
- run() wiring: one ``proposal.stuck_deferred_terminal::<pid>`` self_resolve
  finding per proposal (deduped against existing), the reconcile call, the
  ``reconciled_proposals`` / ``stuck_deferred_terminal`` report counters, and
  the resolve pass clearing the finding once the row disappears;
- fail-soft: a raising predicate leaves the findings where they are.

Same harness as test_proposal_pipeline_shop_manager_redrive_cap.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.proposal_pipeline_shop_manager import (
    _SUBJECT_STUCK_DEFERRED_TERMINAL,
    ProposalPipelineShopManager,
)


_PID = "pid-terminal"


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "proposal_id": _PID,
        "proposal_status": "failed",
        "constitutional_constraints": {},
        "nothing_to_commit": False,
        "finding_ids": ["f-1", "f-2"],
        "seconds_stuck": 4_000_000,
    }
    base.update(overrides)
    return base


def _make_worker() -> ProposalPipelineShopManager:
    w = object.__new__(ProposalPipelineShopManager)
    w._declaration = {}
    w._max_interval = 300
    w.post_heartbeat = AsyncMock()  # type: ignore[method-assign]
    w.post_finding = AsyncMock()  # type: ignore[method-assign]
    w.post_report = AsyncMock()  # type: ignore[method-assign]
    w.post_observation = AsyncMock()  # type: ignore[method-assign]
    return w


def _routes():
    """Patch every destination at its import site inside the method."""
    return {
        "failed": patch(
            "will.autonomy.proposal_consumer_revival.revive_and_report", AsyncMock()
        ),
        "rejected": patch(
            "will.autonomy.proposal_service.revive_findings_for_rejected_proposal",
            AsyncMock(),
        ),
        "report": patch(
            "will.autonomy.proposal_consumer_revival.report_revival", AsyncMock()
        ),
        "resolve": patch(
            "will.autonomy.proposal_execution_pipeline.resolve_deferred_findings",
            AsyncMock(return_value=True),
        ),
        "noop": patch(
            "will.autonomy.proposal_execution_pipeline.revive_deferred_findings_for_noop",
            AsyncMock(return_value=(True, {"proposal_id": _PID, "revived_count": 2})),
        ),
    }


async def _reconcile(row: dict[str, object]) -> tuple[bool, dict[str, AsyncMock]]:
    worker = _make_worker()
    patches = _routes()
    mocks: dict[str, AsyncMock] = {}
    with (
        patches["failed"] as m_failed,
        patches["rejected"] as m_rejected,
        patches["report"] as m_report,
        patches["resolve"] as m_resolve,
        patches["noop"] as m_noop,
    ):
        mocks.update(
            failed=m_failed,
            rejected=m_rejected,
            report=m_report,
            resolve=m_resolve,
            noop=m_noop,
        )
        result = await worker._reconcile_stuck_deferred_terminal(row)  # type: ignore[attr-defined]
    mocks["worker"] = worker  # type: ignore[assignment]
    return result, mocks


# ---------------------------------------------------------------------------
# Routing table
# ---------------------------------------------------------------------------


# ID: 2f71b633-49fb-40b4-bee4-3576c18a0100
async def test_failed_proposal_routes_to_execution_failure_revival() -> None:
    ok, m = await _reconcile(_row(proposal_status="failed"))
    assert ok is True
    m["failed"].assert_awaited_once()
    args = m["failed"].await_args.args
    assert args[0] is m["worker"] and args[1] == _PID
    assert "stuck_deferred_terminal" in args[2] and "failed" in args[2]
    for other in ("rejected", "resolve", "noop"):
        m[other].assert_not_awaited()


# ID: 62fe6588-a13c-4483-a471-c0114a3a3617
async def test_missing_proposal_routes_like_failed() -> None:
    """The revival predicates key on payload.proposal_id and do not need the
    proposal row; a dangling id is still revivable."""
    ok, m = await _reconcile(_row(proposal_status="missing"))
    assert ok is True
    m["failed"].assert_awaited_once()
    assert "missing" in m["failed"].await_args.args[2]


def _bb_for_reject() -> MagicMock:
    bb = MagicMock()
    revival = {"proposal_id": _PID, "revived_count": 2, "revived_subjects": ["s"]}
    bb.revive_ceremony_findings_for_rejected_proposal = AsyncMock(return_value=revival)
    bb.revive_delegated_findings_for_rejected_proposal = AsyncMock(return_value=revival)
    return bb


async def _reconcile_rejected(constraints: dict) -> tuple[bool, MagicMock, dict]:
    bb = _bb_for_reject()
    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb)
    with patch("body.services.service_registry.service_registry", registry):
        ok, m = await _reconcile(
            _row(proposal_status="rejected", constitutional_constraints=constraints)
        )
    return ok, bb, m


# ID: c6b0c552-ff75-4722-a31c-502cd774846a
async def test_rejected_autonomous_proposal_is_delegated_not_reproposed() -> None:
    """The live reject path would send an autonomous-lineage finding back to
    awaiting_reaudit and so to a fresh proposal. The terminate-side branch
    must not: it goes to the governor inbox through the indeterminate+human
    predicate, and never touches the live routing."""
    ok, bb, m = await _reconcile_rejected({})
    assert ok is True
    bb.revive_ceremony_findings_for_rejected_proposal.assert_awaited_once()
    kwargs = bb.revive_ceremony_findings_for_rejected_proposal.await_args.kwargs
    assert kwargs["proposal_id"] == _PID and "governor" in kwargs["reason"]
    bb.revive_delegated_findings_for_rejected_proposal.assert_not_awaited()
    m["rejected"].assert_not_awaited()  # the live-path routing is not used
    m["failed"].assert_not_awaited()
    m["report"].assert_awaited_once()
    assert m["report"].await_args.args[0] is m["worker"]
    assert (
        m["report"].await_args.kwargs["report_subject_family"]
        == "proposal.stuck_deferred_terminal.delegated"
    )


# ID: 5ba1c18b-f3d2-4d58-ad9d-851e1f1657be
async def test_rejected_assisted_lane_proposal_keeps_its_own_predicate() -> None:
    ok, bb, m = await _reconcile_rejected({"assisted_lane": {"agent": "x"}})
    assert ok is True
    bb.revive_delegated_findings_for_rejected_proposal.assert_awaited_once()
    bb.revive_ceremony_findings_for_rejected_proposal.assert_not_awaited()
    m["rejected"].assert_not_awaited()


# ID: 5fa4dda4-de57-45ac-a2e0-074be37eab77
async def test_completed_with_real_commit_resolves() -> None:
    ok, m = await _reconcile(_row(proposal_status="completed", nothing_to_commit=False))
    assert ok is True
    m["resolve"].assert_awaited_once_with(_PID)
    m["noop"].assert_not_awaited()
    m["report"].assert_not_awaited()


# ID: b712595c-74f2-4717-ae6e-8a3c54168d3a
async def test_completed_noop_takes_the_d10_revival() -> None:
    ok, m = await _reconcile(_row(proposal_status="completed", nothing_to_commit=True))
    assert ok is True
    m["noop"].assert_awaited_once_with(_PID)
    m["resolve"].assert_not_awaited()
    m["report"].assert_awaited_once()
    assert (
        m["report"].await_args.kwargs["report_subject_family"]
        == "proposal.noop.revival"
    )


# ID: 8c21d485-2f32-4287-83e8-90c0624fea95
async def test_no_proposal_id_and_raising_predicate_are_fail_soft() -> None:
    ok, m = await _reconcile(_row(proposal_id=None))
    assert ok is False
    m["failed"].assert_not_awaited()

    worker = _make_worker()
    with patch(
        "will.autonomy.proposal_consumer_revival.revive_and_report",
        AsyncMock(side_effect=RuntimeError("db down")),
    ):
        assert (
            await worker._reconcile_stuck_deferred_terminal(  # type: ignore[attr-defined]
                _row(proposal_status="failed")
            )
            is False
        )


# ---------------------------------------------------------------------------
# run() wiring
# ---------------------------------------------------------------------------


def _make_services(rows: list[dict[str, object]], existing: list[dict[str, str]]):
    proposal_svc = MagicMock()
    for name in (
        "fetch_stuck_approved",
        "fetch_stuck_executing",
        "fetch_stuck_finalizing",
        "fetch_stuck_undeferred",
        "fetch_repeated_failures",
    ):
        setattr(proposal_svc, name, AsyncMock(return_value=[]))
    proposal_svc.fetch_stuck_deferred_terminal = AsyncMock(return_value=rows)

    async def _fetch_open(prefix: str, limit: int) -> list[dict[str, str]]:
        return existing if prefix.startswith(_SUBJECT_STUCK_DEFERRED_TERMINAL) else []

    blackboard_svc = MagicMock()
    blackboard_svc.fetch_open_findings = AsyncMock(side_effect=_fetch_open)
    blackboard_svc.resolve_entries = AsyncMock()
    return proposal_svc, blackboard_svc


async def _run_cycle(worker, proposal_svc, blackboard_svc) -> None:
    registry = MagicMock()
    registry.get_proposal_supervision_service = AsyncMock(return_value=proposal_svc)
    registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)
    with patch("body.services.service_registry.service_registry", registry):
        await worker.run()


# ID: 1416fd5c-3879-4230-9ffd-b82f921fc7da
async def test_run_reconciles_posts_finding_and_counts() -> None:
    worker = _make_worker()
    worker._reconcile_stuck_deferred_terminal = AsyncMock(  # type: ignore[method-assign]
        return_value=True
    )
    proposal_svc, blackboard_svc = _make_services([_row()], existing=[])

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    proposal_svc.fetch_stuck_deferred_terminal.assert_awaited_once()
    worker._reconcile_stuck_deferred_terminal.assert_awaited_once_with(_row())
    posted = [c.kwargs for c in worker.post_finding.await_args_list]
    assert len(posted) == 1
    assert posted[0]["subject"] == f"{_SUBJECT_STUCK_DEFERRED_TERMINAL}::{_PID}"
    assert posted[0]["resolution_mechanism"] == "self_resolve"
    assert posted[0]["payload"]["proposal_status"] == "failed"
    assert posted[0]["payload"]["finding_ids"] == ["f-1", "f-2"]
    report = worker.post_report.await_args.kwargs["payload"]
    assert report["stuck_deferred_terminal"] == 1
    assert report["reconciled_proposals"] == 1
    assert report["flagged"] == 1


# ID: 868cab7b-e5a9-4210-b668-00af91bbfff8
async def test_run_dedups_existing_finding_and_still_reconciles() -> None:
    worker = _make_worker()
    worker._reconcile_stuck_deferred_terminal = AsyncMock(  # type: ignore[method-assign]
        return_value=False
    )
    subject = f"{_SUBJECT_STUCK_DEFERRED_TERMINAL}::{_PID}"
    proposal_svc, blackboard_svc = _make_services(
        [_row()], existing=[{"subject": subject, "id": "entry-1"}]
    )

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    worker._reconcile_stuck_deferred_terminal.assert_awaited_once()
    worker.post_finding.assert_not_awaited()
    blackboard_svc.resolve_entries.assert_not_awaited()  # still flagged this cycle
    report = worker.post_report.await_args.kwargs["payload"]
    assert report["reconciled_proposals"] == 0 and report["flagged"] == 0


# ID: 5dc9fbd8-d9e4-47e0-9ed7-fd24f463d3b6
async def test_run_resolves_the_finding_once_the_row_is_gone() -> None:
    """Resolver ownership (ADR-091 D2 Rev B): the pass is its own resolver —
    after reconciliation the query returns nothing and the open finding is
    resolved by the existing clear pass."""
    worker = _make_worker()
    worker._reconcile_stuck_deferred_terminal = AsyncMock()  # type: ignore[method-assign]
    subject = f"{_SUBJECT_STUCK_DEFERRED_TERMINAL}::{_PID}"
    proposal_svc, blackboard_svc = _make_services(
        [], existing=[{"subject": subject, "id": "entry-1"}]
    )

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    worker._reconcile_stuck_deferred_terminal.assert_not_awaited()
    blackboard_svc.resolve_entries.assert_awaited_once_with(["entry-1"])
    assert worker.post_report.await_args.kwargs["payload"]["resolved"] == 1
