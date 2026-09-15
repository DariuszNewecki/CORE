"""seed.external_run_resources -- the one governed writer for an isolated
external-run database (#894 seeding unit, Governor ruling D).

Three layers:
1. no-DB refusals (seed missing, non-disposable name, invalid definition,
   unknown field) -- return before any session is opened;
2. the PRIMARY isolation proof, for real, against the shared test database:
   current_database() is 'core_test', which is not the run's disposable
   name, so the action refuses without writing (integration);
3. the positive path in a child process bound to a disposable Postgres:
   dry run reports the plan; write=True seeds every row in one transaction;
   a second write refuses because the database is now occupied (integration,
   needs Docker).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from body.atomic.external_run_seed_actions import (
    ACTION_ID,
    action_seed_external_run_resources,
)
from shared.governance_token import authorize_execution
from shared.infrastructure.intent.external_run_seed import load_seed_document


_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]
DISPOSABLE = "core_unitd_0123456789abcdef"


def _seed_dir(tmp_path: Path, **resource_overrides) -> Path:
    d = tmp_path / "seed"
    (d / "llm_resources").mkdir(parents=True)
    resource = {
        "name": "ollama_qwen_coder_3b_trial",
        "env_prefix": "OLLAMA_QWEN_CODER_3B_TRIAL",
        "provided_capabilities": ["planning", "json_output"],
        "model_name": "qwen2.5-coder:3b",
        "model_digest": "f72c60cabf6237b07f6e",
        "api_url": "http://192.168.20.40:11434",
        "locality": "local",
        "is_available": True,
        **resource_overrides,
    }
    (d / "llm_resources" / f"{resource['name']}.yaml").write_text(
        yaml.safe_dump(resource)
    )
    (d / "assignments.yaml").write_text(
        yaml.safe_dump(
            {
                "assignments": [
                    {
                        "role": "Planner",
                        "resource": resource["name"],
                        "priority": 1,
                        "is_active": True,
                    }
                ]
            }
        )
    )
    (d / "system_config.yaml").write_text(
        yaml.safe_dump({"operating_mode": "local_only", "llm_enabled": True})
    )
    return d


async def _run(**kwargs):
    with authorize_execution(ACTION_ID):
        return await action_seed_external_run_resources(
            core_context=MagicMock(), **kwargs
        )


# --- 1. no-DB refusals -------------------------------------------------------------


async def test_refuses_without_seed_or_name(tmp_path: Path) -> None:
    r = await _run(write=True, seed=None, expected_database=DISPOSABLE)
    assert r.ok is False and "seed document is required" in r.data["error"]
    seed = load_seed_document(_seed_dir(tmp_path))
    r = await _run(write=True, seed=seed, expected_database=None)
    assert r.ok is False and "expected_database" in r.data["error"]


@pytest.mark.parametrize("name", ["core", "core_test", "postgres", "mydb"])
async def test_refuses_non_disposable_names_before_connecting(
    tmp_path: Path, name: str
) -> None:
    seed = load_seed_document(_seed_dir(tmp_path))
    r = await _run(write=True, seed=seed, expected_database=name)
    assert r.ok is False and r.data["reason"] == "seed_refused"
    assert name in r.data["error"]


async def test_refuses_invalid_or_unknown_definition_fields(tmp_path: Path) -> None:
    seed = load_seed_document(_seed_dir(tmp_path, locality="orbital"))
    r = await _run(write=False, seed=seed, expected_database=DISPOSABLE)
    assert r.ok is False and "invalid" in r.data["error"]
    assert "ollama_qwen_coder_3b_trial" in r.data["violations"]

    seed = load_seed_document(_seed_dir(tmp_path / "b", surprise=1))
    r = await _run(write=False, seed=seed, expected_database=DISPOSABLE)
    assert r.ok is False
    assert any(
        "unknown fields" in v
        for v in r.data["violations"]["ollama_qwen_coder_3b_trial"]
    )


# --- 2. primary isolation proof against the shared test database -------------------


@pytest.mark.integration
async def test_refuses_when_connected_database_is_not_the_run_database(
    tmp_path: Path,
) -> None:
    """core_test is where this process is bound; the action must see that
    current_database() != the disposable name and refuse -- the proof that
    a name check alone would not have given."""
    seed = load_seed_document(_seed_dir(tmp_path))
    r = await _run(write=True, seed=seed, expected_database=DISPOSABLE)
    assert r.ok is False
    assert "is not the run's isolated database" in r.data["error"]
    assert "core_test" in r.data["error"]


# --- 3. positive path in a child process bound to a disposable database ------------


_CHILD = r"""
import asyncio, json, os, sys
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, os.environ["CORE_SRC"])
from body.atomic.external_run_seed_actions import ACTION_ID, action_seed_external_run_resources
from shared.governance_token import authorize_execution
from shared.infrastructure.intent.external_run_seed import load_seed_document

async def main():
    seed = load_seed_document(Path(sys.argv[1]))
    name = sys.argv[2]
    out = {}
    # Ruling E ordering: roles exist before any assignment references them.
    # Before projection the writer must refuse with a clear reason.
    with authorize_execution(ACTION_ID):
        early = await action_seed_external_run_resources(core_context=MagicMock(), write=True, seed=seed, expected_database=name)
        out["before_roles"] = {"ok": early.ok, "data": early.data}
    from body.atomic.cognitive_role_projection_actions import action_project_cognitive_roles
    with authorize_execution("project.cognitive_roles"):
        proj = await action_project_cognitive_roles(core_context=MagicMock(), write=True)
        out["projection"] = {"ok": proj.ok, "created": proj.data.get("created")}
    with authorize_execution(ACTION_ID):
        dry = await action_seed_external_run_resources(core_context=MagicMock(), write=False, seed=seed, expected_database=name)
        out["dry"] = {"ok": dry.ok, "data": dry.data}
        wet = await action_seed_external_run_resources(core_context=MagicMock(), write=True, seed=seed, expected_database=name)
        out["wet"] = {"ok": wet.ok, "data": wet.data}
        again = await action_seed_external_run_resources(core_context=MagicMock(), write=True, seed=seed, expected_database=name)
        out["again"] = {"ok": again.ok, "data": again.data}
    from shared.infrastructure.database.session_manager import get_session
    from sqlalchemy import text
    async with get_session() as s:
        out["rows"] = {
            "llm_resources": [list(r) for r in (await s.execute(text("select name, model_name, is_available from core.llm_resources"))).all()],
            "assignments": [list(r) for r in (await s.execute(text("select role, resource, priority, is_active from core.role_resource_assignments"))).all()],
            "system_config": [list(r) for r in (await s.execute(text("select operating_mode, llm_enabled from core.system_config"))).all()],
        }
    print(json.dumps(out, default=str))

asyncio.run(main())
"""


@pytest.mark.integration
def test_child_process_seeds_disposable_database_once(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "tests" / "fixtures" / "external_target"))
    from db_provisioning import (  # type: ignore[import-not-found]
        start_disposable_database,
        stop_disposable_database,
    )

    seed_dir = _seed_dir(tmp_path)
    script = tmp_path / "child.py"
    script.write_text(_CHILD)
    db = start_disposable_database()
    try:
        env = {k: v for k, v in os.environ.items() if k not in ("REPO_PATH", "MIND")}
        env["DATABASE_URL"] = db.database_url
        env["CORE_SRC"] = str(REPO_ROOT / "src")
        completed = subprocess.run(
            [sys.executable, str(script), str(seed_dir), db.db_name],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
    finally:
        stop_disposable_database(db)
    assert completed.returncode == 0, completed.stderr[-3000:]
    out = json.loads(completed.stdout.strip().splitlines()[-1])
    assert out["before_roles"]["ok"] is False
    assert "project roles first" in out["before_roles"]["data"]["error"]
    assert out["projection"]["ok"] is True, out["projection"]
    assert "Planner" in out["projection"]["created"], (
        "roles come from the copy's taxonomy"
    )
    assert out["dry"]["ok"] is True and out["dry"]["data"]["dry_run"] is True
    assert out["wet"]["ok"] is True, out["wet"]["data"]
    assert out["wet"]["data"]["dry_run"] is False
    assert out["wet"]["data"]["database"] == db.db_name
    assert out["again"]["ok"] is False
    assert "already carries seedable rows" in out["again"]["data"]["error"]
    rows = out["rows"]
    assert [r[0] for r in rows["llm_resources"]] == ["ollama_qwen_coder_3b_trial"]
    assert rows["llm_resources"][0][1] == "qwen2.5-coder:3b"
    assert rows["assignments"][0][:3] == ["Planner", "ollama_qwen_coder_3b_trial", 1]
    assert rows["system_config"] == [["local_only", True]]
