"""The promotion summary carries CORE's open alarms for the governor (#1243)."""

from __future__ import annotations

import pytest

from will.audit_violation import governor_alarms
from will.audit_violation.staleness import STALE_SUBJECT


class _Board:
    def __init__(self, open_subjects: set[str] | Exception) -> None:
        self.open_subjects = open_subjects

    async def fetch_open_finding_subjects_by_prefix(self, prefix: str) -> set[str]:
        if isinstance(self.open_subjects, Exception):
            raise self.open_subjects
        return {s for s in self.open_subjects if s.startswith(prefix)}


@pytest.fixture
def board(monkeypatch: pytest.MonkeyPatch):
    def install(open_subjects: set[str] | Exception) -> None:
        monkeypatch.setattr(
            governor_alarms, "BlackboardQueryService", lambda: _Board(open_subjects)
        )

    return install


async def test_an_open_stale_clone_finding_is_an_alarm_with_the_fix(board) -> None:
    board({STALE_SUBJECT})
    alarms = await governor_alarms.open_alarms()
    assert len(alarms) == 1
    assert "behind main" in alarms[0]
    assert "reset --hard origin/main" in alarms[0]


async def test_no_open_finding_no_alarm(board) -> None:
    board({"something.else::x"})
    assert await governor_alarms.open_alarms() == []


async def test_an_unreadable_board_is_itself_an_alarm(board) -> None:
    board(RuntimeError("db down"))
    assert await governor_alarms.open_alarms() == [
        "CORE could not read its open findings: RuntimeError: db down"
    ]
