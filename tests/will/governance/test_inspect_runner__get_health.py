# tests/will/governance/test_inspect_runner__get_health.py

"""get_health (``core status``): every part answers on its own, read-only."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from will.governance.inspect_runner import get_health


class _Session:
    """Answers each query by a substring of its SQL; one query fails."""

    def __init__(self, answers: dict[str, list[tuple]], failing: str) -> None:
        self.answers = answers
        self.failing = failing
        self.savepoints = 0

    @asynccontextmanager
    async def _nested(self):
        self.savepoints += 1
        yield

    def begin_nested(self):
        return self._nested()

    async def execute(self, statement):
        sql = str(statement)
        if self.failing in sql:
            raise RuntimeError("relation does not exist")
        for key, rows in self.answers.items():
            if key in sql:
                result = MagicMock()
                result.fetchall.return_value = rows
                return result
        raise AssertionError(f"unexpected query: {sql}")


async def test_one_failing_part_does_not_hide_the_others() -> None:
    created = datetime(2026, 10, 1, tzinfo=UTC)
    session = _Session(
        {
            "count(DISTINCT subject)": [],
            "GROUP BY 1, 2": [("finding", "open", 3)],
            "ORDER BY created_at LIMIT 1": [("x::y", created, 600)],
            "split_part": [("proposal.stuck_approved", 1, 60)],
            "FILTER": [(10, 7, 1)],
        },
        failing="core.autonomous_proposals",
    )
    with patch(
        "will.governance.daemon_runner.get_status",
        AsyncMock(return_value={"workers": []}),
    ):
        health = await get_health(session)

    assert health["blackboard"] == [
        {"entry_type": "finding", "status": "open", "count": 3}
    ]
    assert health["oldest_open_finding"]["age_sec"] == 600
    assert health["stuck"][0]["signal"] == "proposal.stuck_approved"
    assert "error" in health["proposals"]
    assert health["last_7_days"] == {
        "findings_created": 10,
        "findings_resolved": 7,
        "findings_abandoned": 1,
    }
    assert session.savepoints == 6


async def test_findings_per_rule_name_the_rule_and_count_repeats() -> None:
    session = _Session(
        {
            "count(DISTINCT subject)": [
                ("architecture.intent.references_resolve", 40, 2, 0, 38),
                ("thesis.broken", 3, 3, 1, 0),
            ],
            "GROUP BY 1, 2": [],
            "ORDER BY created_at LIMIT 1": [],
            "split_part(subject, '::', 1), count(*), ": [],
            "core.autonomous_proposals": [],
            "FILTER": [(43, 1, 38)],
        },
        failing="never-matches",
    )
    with patch(
        "will.governance.daemon_runner.get_status",
        AsyncMock(return_value={"workers": []}),
    ):
        health = await get_health(session)

    assert health["last_7_days_by_rule"][0] == {
        "rule": "architecture.intent.references_resolve",
        "findings_created": 40,
        "subjects_created": 2,
        "findings_resolved": 0,
        "findings_abandoned": 38,
    }
    assert len(health["last_7_days_by_rule"]) == 2


def test_an_audit_finding_belongs_to_its_rule_not_to_audit_violation() -> None:
    from will.governance import inspect_runner

    sql = inspect_runner._RULE_OF_SUBJECT
    assert "audit.violation::%" in sql and "split_part(subject, '::', 2)" in sql
