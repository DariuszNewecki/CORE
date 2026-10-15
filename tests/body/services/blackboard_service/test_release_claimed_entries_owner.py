"""release_claimed_entries releases only the releasing worker's claims (#899).

No real DB: a fake session plays the table. One entry claimed by worker A;
worker B's release is a no-op, worker A's release reopens it.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import patch

from body.services.blackboard_service.blackboard_service import BlackboardService
from body.services.service_registry import ServiceRegistry


ENTRY = "11111111-1111-4111-8111-111111111111"
WORKER_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
WORKER_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class _Table:
    """One claimed row; the UPDATE succeeds only when its predicates hold."""

    def __init__(self) -> None:
        self.row = {"id": ENTRY, "status": "claimed", "claimed_by": str(WORKER_A)}
        self.statements: list[str] = []

    async def execute(self, stmt, params):
        sql = str(stmt)
        self.statements.append(sql)
        owner_checked = "claimed_by = cast(:claimed_by as uuid)" in sql
        hit = (
            params["entry_id"] == self.row["id"]
            and self.row["status"] == "claimed"
            and (not owner_checked or params["claimed_by"] == self.row["claimed_by"])
        )
        if hit:
            self.row.update(status="open", claimed_by=None)
        return type("R", (), {"rowcount": 1 if hit else 0})()

    @asynccontextmanager
    async def begin(self):
        yield


def _patched(table: _Table):
    @asynccontextmanager
    async def _session():
        yield table

    return patch.object(ServiceRegistry, "session", _session)


# ID: 85ebed5b-793d-4a6b-b501-6b9033ba463d
async def test_another_workers_release_is_a_no_op() -> None:
    table = _Table()
    with _patched(table):
        released = await BlackboardService().release_claimed_entries(
            [ENTRY], claimed_by=WORKER_B
        )
    assert released == 0
    assert table.row == {"id": ENTRY, "status": "claimed", "claimed_by": str(WORKER_A)}


# ID: 5859a69b-fe28-44b8-abd7-04beb9b99688
async def test_the_claiming_worker_releases_its_own_claim() -> None:
    table = _Table()
    with _patched(table):
        released = await BlackboardService().release_claimed_entries(
            [ENTRY], claimed_by=WORKER_A
        )
    assert released == 1
    assert table.row["status"] == "open" and table.row["claimed_by"] is None
