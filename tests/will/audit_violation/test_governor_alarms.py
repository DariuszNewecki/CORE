"""The promotion summary carries CORE's open alarms for the governor (#1243)."""

from __future__ import annotations

import json

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


async def test_an_open_stale_clone_finding_is_an_alarm_with_the_fix(
    board, tmp_path
) -> None:
    board({STALE_SUBJECT})
    alarms = await governor_alarms.open_alarms(tmp_path / "no-ledger.jsonl")
    assert len(alarms) == 1
    assert "behind main" in alarms[0]
    assert "reset --hard origin/main" in alarms[0]


async def test_no_open_finding_no_alarm(board, tmp_path) -> None:
    board({"something.else::x"})
    assert await governor_alarms.open_alarms(tmp_path / "no-ledger.jsonl") == []


async def test_an_unreadable_board_is_itself_an_alarm(board, tmp_path) -> None:
    board(RuntimeError("db down"))
    assert await governor_alarms.open_alarms(tmp_path / "no-ledger.jsonl") == [
        "CORE could not read its open findings: RuntimeError: db down"
    ]


def _ledger(tmp_path, *entries: dict):
    path = tmp_path / "deploy-ledger.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return path


def test_a_dev_checkout_left_behind_by_the_last_deploy_is_an_alarm(tmp_path) -> None:
    ledger = _ledger(
        tmp_path,
        {"action": "deploy", "ref": "a" * 40, "dev_checkout": "moved x -> y"},
        {
            "action": "deploy",
            "ref": "c2c7468e45a0d2fb",
            "at": "2026-10-23T02:30:36+00:00",
            "dev_checkout": "not moved: git refused",
        },
        {"action": "rollback-note"},
    )
    (alarm,) = governor_alarms.deploy_alarms(ledger)
    assert "did not follow the last deploy (`c2c7468e45a0`" in alarm
    assert "not moved: git refused" in alarm


def test_a_dev_checkout_that_moved_or_had_nothing_to_do_is_no_alarm(tmp_path) -> None:
    moved = _ledger(tmp_path, {"action": "deploy", "dev_checkout": "moved a -> b"})
    assert governor_alarms.deploy_alarms(moved) == []
    (tmp_path / "x").mkdir()
    same = _ledger(tmp_path / "x", {"action": "deploy", "dev_checkout": None})
    assert governor_alarms.deploy_alarms(same) == []
    assert governor_alarms.deploy_alarms(tmp_path / "absent.jsonl") == []
    (tmp_path / "r").mkdir()  # a rollback leaves the checkout ahead: not stale
    ahead = _ledger(
        tmp_path / "r", {"action": "deploy", "dev_checkout": "not moved: not behind"}
    )
    assert governor_alarms.deploy_alarms(ahead) == []


async def test_open_alarms_carries_the_deploy_alarm(board, tmp_path) -> None:
    board(set())
    ledger = _ledger(
        tmp_path,
        {"action": "deploy", "dev_checkout": "not moved: governed text differs"},
    )
    (alarm,) = await governor_alarms.open_alarms(ledger)
    assert "did not follow the last deploy" in alarm
