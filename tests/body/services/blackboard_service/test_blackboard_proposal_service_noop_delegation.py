# tests/body/services/blackboard_service/test_blackboard_proposal_service_noop_delegation.py
"""Hermetic shape tests for
``BlackboardProposalService.revive_or_delegate_findings_for_noop_proposal``
(ADR-104 D10, #901).

The live behaviour is proven by the integration file
``blackboard_service/test_noop_cap_delegation.py``; this file pins what the
integration DB cannot see — the *shape of the writes* D10 decided on:

- the at-cap terminal is written in this method's own SET clause as the
  literals ``status = 'indeterminate'`` and ``resolution_mechanism = 'human'``
  (``indeterminate_requires_human_mechanism`` reads the literal where it is
  written; no terminal-state parameter reaches the D9 predicate);
- the below-cap write is the D9 revival (``awaiting_reaudit``, reaudit
  guard in the WHERE, counter incremented);
- the partition is on ``(count + 1) >= cap`` and the return dict carries
  ``delegated_*`` in place of ``abandoned_*``.

ServiceRegistry.session is patched to a fake whose execute() records every
statement and answers the SELECT with canned rows.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from body.services.blackboard_service.blackboard_proposal_service import (
    BlackboardProposalService,
)
from body.services.service_registry import ServiceRegistry


class _FakeResult:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return self._rows


@asynccontextmanager
async def _ctx(obj):  # type: ignore[no-untyped-def]
    yield obj


def _session(select_rows: list[tuple]) -> AsyncMock:
    session = AsyncMock()
    session.begin = MagicMock(return_value=_ctx(None))
    calls: list[tuple[str, dict]] = []

    async def _execute(stmt, params=None):  # type: ignore[no-untyped-def]
        calls.append((str(stmt), params or {}))
        if str(stmt).lstrip().upper().startswith("SELECT"):
            return _FakeResult(select_rows)
        return _FakeResult([])

    session.execute = AsyncMock(side_effect=_execute)
    session.calls = calls
    return session


async def _run(select_rows: list[tuple], cap: int = 3):
    session = _session(select_rows)
    with patch.object(ServiceRegistry, "session", return_value=_ctx(session)):
        revival = await BlackboardProposalService().revive_or_delegate_findings_for_noop_proposal(
            proposal_id="pid-noop", reason="nothing to commit", remediation_cap_n=cap
        )
    return revival, session.calls


def _updates(calls: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    return [(sql, p) for sql, p in calls if sql.lstrip().upper().startswith("UPDATE")]


# ID: 635fc4b2-266b-4065-a43b-497214c34fe3
async def test_at_cap_writes_indeterminate_and_human_in_one_set_clause() -> None:
    revival, calls = await _run([("f-1", "python::rule::a.py", 2)])

    updates = _updates(calls)
    assert len(updates) == 1
    sql, params = updates[0]
    set_clause = sql[sql.upper().index("SET") : sql.upper().index("WHERE")]
    assert "status = 'indeterminate'" in set_clause
    assert "resolution_mechanism = 'human'" in set_clause
    assert "'{remediation_attempt_count}'" in set_clause
    assert "'noop_cap_delegated'" in set_clause
    assert "status = 'deferred_to_proposal'" in sql[sql.upper().index("WHERE") :]
    assert params["ids"] == ["f-1"] and params["proposal_id"] == "pid-noop"
    assert revival == {
        "proposal_id": "pid-noop",
        "failure_reason": "nothing to commit",
        "revived_count": 0,
        "revived_finding_ids": [],
        "revived_subjects": [],
        "delegated_count": 1,
        "delegated_finding_ids": ["f-1"],
        "delegated_subjects": ["python::rule::a.py"],
    }


# ID: 7828d014-0475-4512-b86f-0ccf92dc3ff9
async def test_below_cap_writes_the_d9_revival() -> None:
    revival, calls = await _run([("f-1", "python::rule::a.py", 0)])

    updates = _updates(calls)
    assert len(updates) == 1
    sql, params = updates[0]
    set_clause = sql[sql.upper().index("SET") : sql.upper().index("WHERE")]
    assert "status = 'awaiting_reaudit'" in set_clause
    assert "indeterminate" not in sql
    assert "resolution_mechanism = 'reaudit'" in sql[sql.upper().index("WHERE") :]
    assert params == {"ids": ["f-1"]}
    assert revival is not None
    assert revival["revived_finding_ids"] == ["f-1"]
    assert revival["delegated_count"] == 0


# ID: 781cb1c3-8e2e-4745-907a-64a245d3bfd3
async def test_partition_is_on_the_attempt_this_noop_represents() -> None:
    """count 1 → 2 (< 3) revives; count 2 → 3 (>= 3) delegates; both in one
    call, each through its own statement. Nothing deferred → None."""
    revival, calls = await _run(
        [("f-under", "python::rule::a.py", 1), ("f-at", "python::rule::b.py", 2)]
    )
    updates = _updates(calls)
    assert len(updates) == 2
    assert revival is not None
    assert revival["revived_finding_ids"] == ["f-under"]
    assert revival["delegated_finding_ids"] == ["f-at"]

    revival, calls = await _run([])
    assert revival is None
    assert _updates(calls) == []
