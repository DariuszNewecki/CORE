"""ADR-169 D1: a state observation captures HEAD, dirty paths, the law relation
and (at boot) the loaded code identity, and is written as one append-only
INSERT."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from body.services.state_ledger_service import StateLedgerService, observe_state
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

    obs = observe_state(repo, repo / ".intent", "boot", include_code_identity=True)

    assert obs.trigger == "boot"
    assert obs.head_sha and len(obs.head_sha) == 40
    assert obs.dirty_paths == [".intent/law.yaml", "src/app.py"]
    assert obs.law_state.relationship == "DRIFT"
    assert obs.law_state.drift_paths == [".intent/law.yaml"]
    assert obs.loaded_code_identity and len(obs.loaded_code_identity) == 64


def test_code_identity_follows_src_content(repo: Path) -> None:
    before = observe_state(repo, repo / ".intent", "boot", include_code_identity=True)
    (repo / "src/app.py").write_text("x = 3\n")
    after = observe_state(repo, repo / ".intent", "boot", include_code_identity=True)
    assert before.loaded_code_identity != after.loaded_code_identity


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
