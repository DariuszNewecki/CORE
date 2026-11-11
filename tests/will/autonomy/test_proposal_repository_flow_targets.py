"""ProposalRepository.flow_targets sees every proposal in flight.

The test remediator's per-symbol dedup used to read ``list_by_status``,
which returns only the newest ``list_limit`` (500) rows per status. With
more than 500 approved proposals queued, an older proposal for a symbol was
invisible and the remediator minted another one for the same symbol:
about 136,000 approved flow.build_test_for_symbol proposals for 761 symbols
(2026-10-29..31), and duplicate generated tests on main.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_repository import ProposalRepository


pytestmark = [pytest.mark.integration]

_FLOW = "flow.build_test_for_symbol"
_KEYS = ("source_file", "symbol_name")

_INSERT = text(
    """
    INSERT INTO core.autonomous_proposals
        (proposal_id, goal, status, actions, approval_authority, created_at)
    SELECT
        'p-' || n,
        'test',
        CAST(:status AS text),
        jsonb_build_array(jsonb_build_object(
            'order', 0, 'flow_id', CAST(:flow AS text), 'action_id', NULL,
            'parameters', jsonb_build_object(
                'source_file', 'src/m' || n || '.py', 'symbol_name', 'f' || n))),
        'risk_classification.safe_auto_approval',
        now() - (n || ' minutes')::interval
    FROM generate_series(CAST(:first AS int), CAST(:last AS int)) AS n
    """
)


async def _insert(session: AsyncSession, first: int, last: int, **kw) -> None:
    params = {"status": "approved", "flow": _FLOW, "first": first, "last": last}
    params.update(kw)
    await session.execute(_INSERT, params)
    await session.commit()


@pytest.mark.asyncio
# ID: 3c9e1f7a-5b2d-4e8c-a6f0-9d1b4c7e2a58
async def test_flow_targets_sees_proposals_beyond_list_limit(
    db_session: AsyncSession,
) -> None:
    # 600 approved proposals; n=600 is the oldest, past the newest 500.
    await _insert(db_session, 1, 600)
    repo = ProposalRepository(db_session)

    targets = await repo.flow_targets(_FLOW, {ProposalStatus.APPROVED}, _KEYS)

    assert len(targets) == 600
    assert ("src/m600.py", "f600") in targets
    # The old dedup read (limit=500, newest first) cannot see it: the bug.
    newest = await repo.list_by_status(ProposalStatus.APPROVED, limit=500)
    assert len(newest) == 500
    assert all(p.proposal_id != "p-600" for p in newest)


@pytest.mark.asyncio
# ID: 8a4d2e6b-1f9c-4b3a-9e7d-5c0f2b8a6d14
async def test_flow_targets_filters_status_and_flow(db_session: AsyncSession) -> None:
    await _insert(db_session, 1, 2)
    await _insert(db_session, 3, 3, status="completed")
    await _insert(db_session, 4, 4, flow="flow.other")
    repo = ProposalRepository(db_session)

    targets = await repo.flow_targets(
        _FLOW, {ProposalStatus.APPROVED, ProposalStatus.PENDING}, _KEYS
    )

    assert targets == {("src/m1.py", "f1"), ("src/m2.py", "f2")}
