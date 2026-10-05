"""ADR-169 D1: a state observation captures HEAD, dirty paths, the law relation
and the loaded code identity it is given, and is written as one append-only
INSERT -- per cycle only when the state changed."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from body.services.state_ledger_service import (
    StateLedgerService,
    observation_key,
    observe_state,
)
from shared.infrastructure.intent.law_state import LawState


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / ".intent").mkdir()
    (tmp_path / ".intent/law.yaml").write_text("x: 1\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_boot_observation_records_head_dirt_law_and_code(repo: Path) -> None:
    (repo / "src/app.py").write_text("x = 2\n")
    (repo / ".intent/law.yaml").write_text("x: 2\n")

    obs = observe_state(repo, repo / ".intent", "boot", loaded_code_identity="f" * 64)

    assert obs.trigger == "boot"
    assert obs.head_sha and len(obs.head_sha) == 40
    assert obs.dirty_paths == [".intent/law.yaml", "src/app.py"]
    assert obs.law_state.relationship == "DRIFT"
    assert obs.law_state.drift_paths == [".intent/law.yaml"]
    assert obs.loaded_code_identity == "f" * 64


def test_loaded_code_identity_is_recorded_as_given_not_recomputed(
    repo: Path,
) -> None:
    """The code on disk now is not necessarily the code the process runs."""
    (repo / "src/app.py").write_text("x = 3\n")
    obs = observe_state(repo, repo / ".intent", "cycle", loaded_code_identity="old")
    assert obs.loaded_code_identity == "old"


def test_audit_run_observation_reuses_the_verdicts_law_state(repo: Path) -> None:
    """The ledger row and the verdict describe the same observation."""
    law = LawState(relationship="MATCH", head_sha="b" * 40, record_digest="d")
    obs = observe_state(
        repo, repo / ".intent", "audit_run", law_state=law, audit_run_id="r1"
    )
    assert obs.law_state is law
    assert obs.audit_run_id == "r1"
    assert obs.loaded_code_identity is None


async def test_record_is_one_insert_with_the_observation(repo: Path) -> None:
    obs = observe_state(repo, repo / ".intent", "boot")
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    await StateLedgerService().record(session, obs)

    sql = str(session.execute.await_args.args[0])
    params = session.execute.await_args.args[1]
    assert "INSERT INTO core.state_observations" in sql
    assert "UPDATE" not in sql
    assert params["trigger"] == "boot"
    assert params["relationship"] == "MATCH"
    assert json.loads(params["dirty"]) == []
    session.commit.assert_awaited_once()


def _session_with_latest(row: dict | None) -> MagicMock:
    session = MagicMock()
    latest = MagicMock()
    latest.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(side_effect=[latest, MagicMock()])
    session.commit = AsyncMock()
    return session


def _row_of(obs) -> dict:
    law = obs.law_state
    return {
        "head_sha": obs.head_sha,
        "dirty_paths": obs.dirty_paths,
        "law_relationship": law.relationship,
        "law_record_digest": law.record_digest,
        "law_evaluated_digest": law.evaluated_digest,
        "law_drift_paths": law.drift_paths,
        "loaded_code_identity": obs.loaded_code_identity,
    }


async def test_unchanged_state_appends_no_row(repo: Path) -> None:
    obs = observe_state(repo, repo / ".intent", "cycle", loaded_code_identity="c")
    session = _session_with_latest(_row_of(obs))

    assert await StateLedgerService().record_if_changed(obs, session) is False
    assert session.execute.await_count == 1  # the SELECT only
    session.commit.assert_not_awaited()


async def test_changed_state_appends_a_row(repo: Path) -> None:
    before = observe_state(repo, repo / ".intent", "cycle", loaded_code_identity="c")
    (repo / ".intent/law.yaml").write_text("x: 9\n")
    after = observe_state(repo, repo / ".intent", "cycle", loaded_code_identity="c")
    session = _session_with_latest(_row_of(before))

    assert await StateLedgerService().record_if_changed(after, session) is True
    insert_sql = str(session.execute.await_args_list[1].args[0])
    assert "INSERT INTO core.state_observations" in insert_sql
    assert session.execute.await_args_list[1].args[1]["trigger"] == "cycle"


async def test_first_observation_is_always_appended(repo: Path) -> None:
    obs = observe_state(repo, repo / ".intent", "cycle")
    session = _session_with_latest(None)
    assert await StateLedgerService().record_if_changed(obs, session) is True


def test_observation_key_reads_jsonb_as_text_or_list() -> None:
    row = {"head_sha": "h", "dirty_paths": '["b", "a"]', "law_drift_paths": []}
    assert observation_key(row) == observation_key(
        {"head_sha": "h", "dirty_paths": ["a", "b"], "law_drift_paths": "[]"}
    )
