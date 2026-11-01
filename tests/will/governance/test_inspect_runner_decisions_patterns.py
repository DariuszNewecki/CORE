"""get_decisions_patterns runs the real repository aggregation (#1386).

It used to call ``repo.get_pattern_stats(days=...)``, a method whose real
signature is ``(pattern_name, limit)``: every request raised TypeError.
Only the database session is faked here; the facade, the repository and
its query run for real.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

from will.governance.inspect_runner import get_decisions_patterns


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _FakeResult(self._rows)


@pytest.mark.asyncio
# ID: 2c1f3c55-7b0e-4a8e-9f61-0d4f3b6b8a10
async def test_get_decisions_patterns_aggregates_traces_in_window():
    rows = [
        ({"action_pattern": 3, "inspect_pattern": 1}, "true"),
        ({"action_pattern": 2}, "false"),
        (None, None),
    ]
    session = _FakeSession(rows)

    @asynccontextmanager
    async def _session():
        yield session

    with patch(
        "body.infrastructure.repositories.decision_trace_repository."
        "service_registry.session",
        _session,
    ):
        result = await get_decisions_patterns(days=3)

    assert result["days"] == 3
    assert result["patterns"] == {
        "action_pattern": {
            "count": 2,
            "violations": 1,
            "decisions": 5,
            "success_rate": 50.0,
        },
        "inspect_pattern": {
            "count": 1,
            "violations": 1,
            "decisions": 1,
            "success_rate": 0.0,
        },
    }
    (stmt,) = session.statements
    sql = str(stmt)
    assert "decision_traces.created_at >=" in sql
    assert stmt.compile().params["created_at_1"] is not None
