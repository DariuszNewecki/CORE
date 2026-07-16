# tests/will/workers/test_proposal_pipeline_shop_manager_redrive_cap.py

"""
ADR-150 D5 fault-injection tests — the finalizing redrive cap.

Asserts the properties that actually hold in the held-open finding
lifecycle (ADR-150 D1/D2/D3):

  1. First detection posts the finding with finalization_redrive_count=1
     when the redrive failed (0 when it advanced) — the D3 re-arm path
     starts fresh the same way.
  2. Below cap: the count is incremented IN PLACE on the same entry_id;
     the finding is NOT re-posted while the proposal stays finalizing.
  3. At finalizing_redrive_cap_n: the finding is escalated
     (indeterminate/human) and the run report counts it.
  4. The escalated finding survives subsequent manager cycles — the
     resolve pass cannot reach it (open-only existing fetch) and the
     supervision query's NOT EXISTS guard keeps the proposal out of the
     redrive set (pinned textually on the SQL).
  5. A successful roll-forward never touches the counter.
  6. Single-statement co-assignment: escalation sets status='indeterminate'
     and resolution_mechanism='human' in ONE UPDATE (blocking rule
     architecture.blackboard.indeterminate_requires_human_mechanism).
"""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.proposal_pipeline_shop_manager import (
    _SUBJECT_STUCK_FINALIZING,
    ProposalPipelineShopManager,
)


_ENTRY_ID = "11111111-2222-3333-4444-555555555555"
_PID = "pid-cap"


def _row() -> dict[str, object]:
    return {
        "proposal_id": _PID,
        "execution_completed_at": None,
        "seconds_stuck": 999,
        "has_consequence": False,
        "execution_results": {},
        "finding_ids": [],
        "policies": [],
    }


def _make_worker(roll_forward_result: bool) -> ProposalPipelineShopManager:
    """Bypass Worker.__init__ (reads .intent/); stub the Worker surface."""
    w = object.__new__(ProposalPipelineShopManager)
    w._declaration = {}
    w._max_interval = 300
    w.post_heartbeat = AsyncMock()  # type: ignore[method-assign]
    w.post_finding = AsyncMock()  # type: ignore[method-assign]
    w.post_report = AsyncMock()  # type: ignore[method-assign]
    w._roll_forward_finalizing = AsyncMock(  # type: ignore[method-assign]
        return_value=roll_forward_result
    )
    return w


def _make_services(
    stuck_finalizing: list[dict[str, object]],
    existing_finalizing: list[dict[str, str]],
    increment_returns: int = 0,
):
    """Mock supervision + blackboard services for one run() cycle."""
    proposal_svc = MagicMock()
    proposal_svc.fetch_stuck_approved = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_executing = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_finalizing = AsyncMock(return_value=stuck_finalizing)
    proposal_svc.fetch_stuck_undeferred = AsyncMock(return_value=[])
    proposal_svc.fetch_repeated_failures = AsyncMock(return_value=[])

    async def _fetch_open(prefix: str, limit: int) -> list[dict[str, str]]:
        if prefix.startswith(_SUBJECT_STUCK_FINALIZING):
            return existing_finalizing
        return []

    blackboard_svc = MagicMock()
    blackboard_svc.fetch_open_findings = AsyncMock(side_effect=_fetch_open)
    blackboard_svc.resolve_entries = AsyncMock()
    blackboard_svc.increment_finding_counter = AsyncMock(
        return_value=increment_returns
    )
    blackboard_svc.escalate_finding_to_governor = AsyncMock(return_value=True)
    return proposal_svc, blackboard_svc


async def _run_cycle(worker, proposal_svc, blackboard_svc) -> None:
    registry = MagicMock()
    registry.get_proposal_supervision_service = AsyncMock(return_value=proposal_svc)
    registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)
    with patch(
        "body.services.service_registry.service_registry",
        registry,
    ):
        await worker.run()


# ---------------------------------------------------------------------------
# 1 + re-arm: first detection seeds the count from this cycle's outcome
# ---------------------------------------------------------------------------


async def test_first_detection_failed_redrive_posts_count_1():
    worker = _make_worker(roll_forward_result=False)
    proposal_svc, blackboard_svc = _make_services([_row()], existing_finalizing=[])

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    payload = worker.post_finding.await_args.kwargs["payload"]
    assert payload["finalization_redrive_count"] == 1
    blackboard_svc.increment_finding_counter.assert_not_awaited()
    blackboard_svc.escalate_finding_to_governor.assert_not_awaited()


async def test_first_detection_advanced_posts_count_0():
    worker = _make_worker(roll_forward_result=True)
    proposal_svc, blackboard_svc = _make_services([_row()], existing_finalizing=[])

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    payload = worker.post_finding.await_args.kwargs["payload"]
    assert payload["finalization_redrive_count"] == 0


# ---------------------------------------------------------------------------
# 2: below cap — in-place increment on the same entry_id, no re-post
# ---------------------------------------------------------------------------


async def test_failed_redrive_increments_in_place_below_cap():
    worker = _make_worker(roll_forward_result=False)
    existing = [{"subject": f"{_SUBJECT_STUCK_FINALIZING}::{_PID}", "id": _ENTRY_ID}]
    proposal_svc, blackboard_svc = _make_services(
        [_row()], existing_finalizing=existing, increment_returns=2
    )

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    blackboard_svc.increment_finding_counter.assert_awaited_once_with(
        _ENTRY_ID, "finalization_redrive_count"
    )
    blackboard_svc.escalate_finding_to_governor.assert_not_awaited()
    # Held-open lifecycle: no re-post while the finding is open.
    worker.post_finding.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3: at cap — escalate, count it in the report
# ---------------------------------------------------------------------------


async def test_cap_reached_escalates_to_governor_and_reports():
    worker = _make_worker(roll_forward_result=False)
    existing = [{"subject": f"{_SUBJECT_STUCK_FINALIZING}::{_PID}", "id": _ENTRY_ID}]
    proposal_svc, blackboard_svc = _make_services(
        [_row()], existing_finalizing=existing, increment_returns=3
    )

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    escalate_call = blackboard_svc.escalate_finding_to_governor.await_args
    assert escalate_call.args[0] == _ENTRY_ID
    merge = escalate_call.args[1]
    assert merge["escalation"] == "finalizing_redrive_cap_reached"
    assert merge["finalization_redrive_count"] == 3

    report = worker.post_report.await_args.kwargs["payload"]
    assert report["escalated_proposals"] == 1


# ---------------------------------------------------------------------------
# 4: the escalated finding survives subsequent cycles
# ---------------------------------------------------------------------------


async def test_escalated_finding_survives_next_cycle():
    """
    After escalation: the finding is 'indeterminate' (invisible to the
    open-only existing fetch) and the proposal is excluded from
    fetch_stuck_finalizing (SQL NOT EXISTS). Next cycle therefore sees
    neither — and the resolve pass must not touch anything.
    """
    worker = _make_worker(roll_forward_result=False)
    proposal_svc, blackboard_svc = _make_services(
        stuck_finalizing=[], existing_finalizing=[]
    )

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    blackboard_svc.resolve_entries.assert_not_awaited()
    worker.post_finding.assert_not_awaited()
    blackboard_svc.escalate_finding_to_governor.assert_not_awaited()


def test_supervision_query_excludes_escalated_proposals():
    """Pin the D2 SQL guard: fetch_stuck_finalizing must carry the
    NOT EXISTS exclusion on indeterminate stuck_finalizing findings."""
    from body.services.proposal_supervision_service import (
        ProposalSupervisionService,
    )

    src = inspect.getsource(ProposalSupervisionService.fetch_stuck_finalizing)
    assert "NOT EXISTS" in src
    assert "proposal.stuck_finalizing::" in src
    assert "'indeterminate'" in src


# ---------------------------------------------------------------------------
# 5: success path never touches the counter
# ---------------------------------------------------------------------------


async def test_advanced_roll_forward_skips_counter():
    worker = _make_worker(roll_forward_result=True)
    existing = [{"subject": f"{_SUBJECT_STUCK_FINALIZING}::{_PID}", "id": _ENTRY_ID}]
    proposal_svc, blackboard_svc = _make_services(
        [_row()], existing_finalizing=existing
    )

    await _run_cycle(worker, proposal_svc, blackboard_svc)

    blackboard_svc.increment_finding_counter.assert_not_awaited()
    blackboard_svc.escalate_finding_to_governor.assert_not_awaited()


# ---------------------------------------------------------------------------
# 6: service-layer contracts (single-statement co-assignment; open-only)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _ctx(value):  # type: ignore[no-untyped-def]
    yield value


def _session_with(result) -> MagicMock:  # type: ignore[no-untyped-def]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.begin = MagicMock(return_value=_ctx(None))
    return session


async def test_escalate_finding_single_statement_co_assignment():
    from body.services.blackboard_service.blackboard_service import BlackboardService
    from body.services.service_registry import ServiceRegistry

    result = MagicMock()
    result.rowcount = 1
    session = _session_with(result)

    svc = object.__new__(BlackboardService)
    with patch.object(ServiceRegistry, "session", return_value=_ctx(session)):
        ok = await svc.escalate_finding_to_governor(_ENTRY_ID, {"cap_n": 3})

    assert ok is True
    sql = str(session.execute.await_args.args[0])
    # The blocking rule requires the co-assignment in the SAME statement.
    assert "status = 'indeterminate'" in sql
    assert "resolution_mechanism = 'human'" in sql
    assert "status = 'open'" in sql  # only open findings are escalatable


async def test_increment_finding_counter_open_only_returns_new_value():
    from body.services.blackboard_service.blackboard_service import BlackboardService
    from body.services.service_registry import ServiceRegistry

    result = MagicMock()
    result.fetchone = MagicMock(return_value=(2,))
    session = _session_with(result)

    svc = object.__new__(BlackboardService)
    with patch.object(ServiceRegistry, "session", return_value=_ctx(session)):
        count = await svc.increment_finding_counter(
            _ENTRY_ID, "finalization_redrive_count"
        )

    assert count == 2
    sql = str(session.execute.await_args.args[0])
    assert "jsonb_set" in sql
    assert "status = 'open'" in sql
