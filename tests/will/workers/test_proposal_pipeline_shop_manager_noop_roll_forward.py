# tests/will/workers/test_proposal_pipeline_shop_manager_noop_roll_forward.py
"""ProposalPipelineShopManager._roll_forward_finalizing honours a no-op
commit (ADR-104 D9 applied to the no-op loop, #901).

The stuck-finalizing reaper re-drives the executor's finalization steps
(ADR-148 D4). If it resolved the deferred findings of a proposal whose
recorded consequence proves the commit changed nothing
(``nothing_to_commit``: pre and post SHA captured and equal), it would
re-create exactly the false "resolved by <proposal>" claim the executor no
longer makes. It must revive them on the capped path instead, post the
record through itself (it is a Worker), and leave the proposal FINALIZING
when the revival fails. A row without the flag keeps the existing resolve
path — pinned as the control.

Sibling of test_proposal_pipeline_shop_manager_roll_forward.py; same
harness.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


@asynccontextmanager
async def _session_ctx(session: MagicMock):  # type: ignore[no-untyped-def]
    yield session


def _make_worker_instance() -> object:
    from will.workers.proposal_pipeline_shop_manager import ProposalPipelineShopManager

    w = object.__new__(ProposalPipelineShopManager)
    w._declaration = {}
    w._max_interval = 300
    return w


def _patch_service_registry(session: MagicMock):  # type: ignore[no-untyped-def]
    import body.services.service_registry as svc_mod

    orig = svc_mod.service_registry
    mock_svc = MagicMock()
    mock_svc.session = MagicMock(return_value=_session_ctx(session))
    svc_mod.service_registry = mock_svc
    return mock_svc, orig, svc_mod


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "proposal_id": "pid-noop-finalizing",
        "has_consequence": True,
        "nothing_to_commit": True,
        "execution_results": {},
        "finding_ids": ["f-1"],
        "policies": [],
    }
    base.update(overrides)
    return base


async def _roll_forward(row: dict[str, object], *, revive_result: object) -> dict:
    worker = _make_worker_instance()
    session = AsyncMock()
    mocks = {
        "resolve": AsyncMock(return_value=True),
        "revive": AsyncMock(return_value=revive_result),
        "report": AsyncMock(),
        "mark_completed": AsyncMock(),
    }
    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with (
            patch(
                "will.autonomy.proposal_execution_pipeline.resolve_deferred_findings",
                mocks["resolve"],
            ),
            patch(
                "will.autonomy.proposal_execution_pipeline"
                ".revive_deferred_findings_for_noop",
                mocks["revive"],
            ),
            patch(
                "will.autonomy.proposal_consumer_revival.report_revival",
                mocks["report"],
            ),
            patch(
                "will.autonomy.proposal_state_manager.ProposalStateManager"
                ".mark_completed",
                mocks["mark_completed"],
            ),
        ):
            mocks["result"] = await worker._roll_forward_finalizing(  # type: ignore[attr-defined]
                row
            )
    finally:
        svc_mod.service_registry = orig
    mocks["worker"] = worker
    return mocks


# ID: adc62277-23c7-4581-bc75-d77125e03e11
async def test_noop_row_revives_reports_and_completes() -> None:
    revival = {"proposal_id": "pid-noop-finalizing", "revived_count": 1}
    m = await _roll_forward(_row(), revive_result=(True, revival))

    assert m["result"] is True
    m["revive"].assert_awaited_once_with("pid-noop-finalizing")
    m["resolve"].assert_not_awaited()
    m["report"].assert_awaited_once_with(
        m["worker"],
        "pid-noop-finalizing",
        revival,
        report_subject_family="proposal.noop.revival",
    )
    m["mark_completed"].assert_awaited_once_with("pid-noop-finalizing")


# ID: 03aa3a5d-d595-419c-8925-131aad407323
async def test_noop_row_with_revival_outage_stays_finalizing() -> None:
    m = await _roll_forward(_row(), revive_result=(False, None))

    assert m["result"] is False
    m["report"].assert_not_awaited()
    m["mark_completed"].assert_not_awaited()


# ID: a1941a17-38d9-4f88-83d3-81d284abbd14
async def test_real_commit_row_keeps_the_resolve_path() -> None:
    m = await _roll_forward(_row(nothing_to_commit=False), revive_result=(True, None))

    assert m["result"] is True
    m["resolve"].assert_awaited_once_with("pid-noop-finalizing")
    m["revive"].assert_not_awaited()
    m["report"].assert_not_awaited()
    m["mark_completed"].assert_awaited_once_with("pid-noop-finalizing")
