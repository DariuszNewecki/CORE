# tests/cli/logic/demo/test_consequence_chain_llm_isolation.py
"""E14 — no LLM env leaks into the child scenario process (ADR-155).

Two structural claims underpin E14: (1) the child scenario process
(``scenario_runner.py``, spawned via ``shared.utils.subprocess_utils.
run_child_process``) never inherits ambient LLM-shaped environment variables
from the parent — ``run_child_process`` passes an explicit, non-merged
``env`` dict to ``asyncio.create_subprocess_exec``, and
``run_consequence_chain`` builds that dict from nothing but ``PATH``; and
(2) the clone's own ``.env`` (written by ``_write_child_env``) hardcodes
``LLM_ENABLED=False`` rather than deriving it from any parent env var.

Follows the same monkeypatch technique as
``test_isolation.py::test_e03_compose_up_env_is_passed_through_verbatim``
(patch ``asyncio.create_subprocess_exec`` inside
``shared.utils.subprocess_utils`` and capture its ``env``/``cwd`` kwargs) and
the same Docker/child boundary patch as
``test_consequence_chain_failure_paths.py`` (``compose_up``/``compose_down``/
``_container_host_port``/``read_state_json`` monkeypatched on the
``cli.logic.demo.consequence_chain`` module) — except here
``run_child_process`` itself is deliberately left UNPATCHED, since it is the
child-spawn boundary under test. Reaching it needs no real Docker: the
Compose/port boundary is faked exactly as the failure-paths suite does.

This proves only what is actually demonstrable in a unit test: no LLM env
value crosses the process-spawn boundary, and the on-disk LLM-disabled
config is deterministic, not ambient-derived. It does NOT claim (and must
not be read as claiming) that no network attempt could ever occur across
the process boundary — that is not provable here.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import cli.logic.demo.consequence_chain as cc
from cli.logic.demo.consequence_chain import run_consequence_chain
from shared.infrastructure.git_service import GitService


_SENTINELS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "sentinel-should-not-leak",
    "OPENAI_API_KEY": "sentinel-should-not-leak",
    "LLM_BASE_URL": "http://sentinel.invalid:1/",
    # Deliberately True in the parent's ambient env, to prove the child's own
    # explicit False (written to its .env by _write_child_env) wins — not an
    # inherited/derived value.
    "LLM_ENABLED": "True",
}


def _ok(returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout="", stderr="")


class _FakeChildProcess:
    """Stands in for the real scenario_runner.py OS process (never actually
    spawned here) — only its ``wait()`` contract is needed by
    ``run_child_process``."""

    async def wait(self) -> int:
        return 0


def _read_state_stub(path: Path) -> dict[str, object]:
    """The real child never ran, so no real scenario_result.json exists.

    This test cares only about the child-spawn boundary's env and the
    on-disk .env content, not the scenario outcome — a minimal,
    explicitly-failed placeholder keeps ``run_consequence_chain`` from
    raising on the missing state file.
    """
    return {
        "run_id": Path(path).parent.name,
        "seed_rel_path": "src/body/analyzers/does_not_matter.py",
        "finding": None,
        "finding_matches_count": 0,
        "proposal": None,
        "chain": None,
        "reaudit_clean": False,
        "reaudit_matches_count": 1,
        "error": "test double — child process spawn was faked",
    }


# ID: 1a1f7e0b-6b8b-4e9a-8a2a-4a0b2f6f4e21
async def test_e14_no_llm_env_leaks_into_child_scenario_process_spawn(
    source_repo: GitService, demo_state_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ambient LLM-shaped env var reaches the real child-spawn call.

    ``run_child_process`` is left unpatched (it's the boundary under test);
    only the Docker-touching calls around it are faked, mirroring
    ``test_consequence_chain_failure_paths.py``'s boundary patch. The
    underlying ``asyncio.create_subprocess_exec`` is captured the same way
    ``test_e03_compose_up_env_is_passed_through_verbatim`` captures it for
    ``compose_up``.
    """
    for key, value in _SENTINELS.items():
        monkeypatch.setenv(key, value)

    async def _compose_up(project: str, compose_file: Path, env: dict, **kw: object):
        return _ok(0)

    async def _compose_down(project: str, compose_file: Path, env: dict, **kw: object):
        return _ok(0)

    async def _port(project: str, service: str, port: int) -> str:
        return "15432"

    captured: dict[str, object] = {}
    real_create_subprocess_exec = asyncio.create_subprocess_exec

    async def _fake_create_subprocess_exec(*args: object, **kwargs: object):
        # Only the scenario_runner.py child spawn is faked here — GitService
        # (e.g. `diff_file_names`) also calls `asyncio.create_subprocess_exec`
        # directly (not through `shared.utils.subprocess_utils`'s own
        # reference to the same, global `asyncio` module), and patching the
        # module attribute patches it everywhere; anything else must pass
        # through to the real implementation unchanged.
        if any("scenario_runner.py" in str(a) for a in args):
            captured["args"] = args
            captured["env"] = kwargs.get("env")
            captured["cwd"] = kwargs.get("cwd")
            return _FakeChildProcess()
        # Passthrough for every other caller (e.g. GitService's own direct
        # asyncio.create_subprocess_exec use) — args/kwargs here are exactly
        # what a real caller supplied, just not statically typed as such
        # through this test double's deliberately-generic capture signature.
        return await real_create_subprocess_exec(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(cc, "compose_up", _compose_up)
    monkeypatch.setattr(cc, "compose_down", _compose_down)
    monkeypatch.setattr(cc, "_container_host_port", _port)
    monkeypatch.setattr(cc, "read_state_json", _read_state_stub)
    monkeypatch.setattr(
        "shared.utils.subprocess_utils.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
    )

    await run_consequence_chain(source_repo, demo_state_root)

    assert "env" in captured, "run_child_process's create_subprocess_exec was never invoked"
    child_env_obj = captured["env"]
    assert isinstance(child_env_obj, dict)
    child_env: dict[str, str] = child_env_obj

    env_str = str(child_env)
    for sentinel in ("sentinel-should-not-leak", "sentinel.invalid"):
        assert sentinel not in env_str, f"sentinel leaked into child spawn env: {child_env}"
    # Structural claim from consequence_chain.py: child_env is built from
    # nothing but PATH — no ambient key survives at all, sentinel or not.
    assert set(child_env) <= {"PATH"}, f"unexpected keys in child spawn env: {child_env}"

    # Second half of E14: the clone's own .env is deterministic, not derived
    # from the parent's ambient LLM_ENABLED=True set above.
    clone_repo_path = captured["cwd"]
    assert clone_repo_path is not None
    env_file = Path(str(clone_repo_path)) / ".env"
    assert env_file.exists(), f"_write_child_env never wrote {env_file}"
    env_file_text = env_file.read_text(encoding="utf-8")
    assert "LLM_ENABLED=False" in env_file_text
    assert "sentinel-should-not-leak" not in env_file_text
