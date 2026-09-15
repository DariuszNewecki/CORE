"""`core-admin runtime external-run` (#894 Unit 2, ADR-159 Note 2026-09-15).

Three layers of proof, each honest about what it covers:

1. **In-process, deterministic** -- `execute()` with the bootstrap, readiness
   and develop dependencies substituted. Proves the orchestration: subject
   fingerprint, evidence-root refusals, materialization (floor-wins with
   preserved originals), environment binding, the bind-time envelope check,
   the explicit UNAVAILABLE outcome, the legacy_direct_write guard, the
   post-run subject-unchanged check, and the evidence files. No DB, no LLM.
2. **Child-process** -- the real `core-admin` entry point, proving early
   dispatch (before the heavy imports) and the pre-bootstrap refusals. No DB.
3. **Live** -- the real run against a disposable Postgres and a reachable
   LLM; opt-in via `CORE_EXTERNAL_RUN_LIVE=1`, otherwise skipped. Expected
   to end UNAVAILABLE on a schema-only database (no cognitive roles seeded):
   Unit 2 does not claim the complete runner is operational.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from cli.runtime_external_run import (
    EXIT_BINDING_REFUSED,
    EXIT_INTERNAL_FAILURE,
    EXIT_RAN,
    EXIT_UNAVAILABLE,
    ExternalRunOptions,
    execute,
    guard_legacy_direct_write,
    matches_route,
)
from shared.infrastructure.intent.machinery_floor_integrity import verify_floor
from shared.infrastructure.intent.target_intent_assembly import subject_fingerprint


_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]
OVERLAY_DIR = _HERE / "intent_overlay"


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _subject(tmp_path: Path, *, with_intent: bool = False) -> Path:
    s = tmp_path / "subject"
    (s / "package").mkdir(parents=True)
    (s / "package" / "mod.py").write_text("x = 1\n")
    if with_intent:
        (s / ".intent" / "rules" / "code").mkdir(parents=True)
        (s / ".intent" / "rules" / "code" / "subject_rule.json").write_text("{}\n")
    _git(["init", "-q"], s)
    _git(["add", "-A"], s)
    _git(["commit", "-q", "-m", "frozen"], s)
    return s


SEED_DIR = _HERE / "seed"


def _opts(
    subject: Path,
    evidence: Path | None,
    overlay: Path | None = OVERLAY_DIR,
    seed: Path | None = SEED_DIR,
) -> ExternalRunOptions:
    return ExternalRunOptions(
        subject=subject,
        goal="Evaluate the package",
        workflow_type="code_modification",
        overlay=overlay,
        evidence_dir=evidence,
        write=False,
        seed=seed,
    )


class _Fakes:
    """Injectable dependencies that record what the route did with them."""

    def __init__(
        self,
        env: dict[str, str] | None = None,
        *,
        readiness_reason: str | None = None,
        develop_ok: bool = True,
    ) -> None:
        # The route binds REPO_PATH/MIND into the environ it was given; the
        # fakes read the same mapping (production passes os.environ).
        self.env: dict[str, str] = env if env is not None else {}
        self.readiness_reason = readiness_reason
        self.develop_ok = develop_ok
        self.bootstrap_env: dict[str, str] = {}
        self.develop_calls: list[tuple[str, str, bool]] = []
        self.develop_env: dict[str, str] = {}
        # a bare object with a settable attribute, like CoreContext
        self.context = type("Ctx", (), {"target_binding": None})()

    async def seed_environment(
        self,
        context: Any,
        seed_dir: Path,
        database_url: str,
        copy: Any,
        evidence_root: Path,
    ) -> str:
        assert context is self.context
        assert seed_dir.is_dir()
        assert evidence_root.name == "evidence"
        self.seeded = True
        assert "QDRANT_URL" not in self.env, (
            "ruling C: unset before any seeding/bootstrap"
        )
        return "5" * 64

    async def cognitive_init(self, context: Any) -> None:
        assert getattr(self, "seeded", False), "cognitive init must follow seeding"

    async def bootstrap(self, expected_target: Path, expected_mind: Path) -> Any:
        self.bootstrap_env = {k: self.env.get(k, "") for k in ("REPO_PATH", "MIND")}
        assert Path(self.bootstrap_env["REPO_PATH"]) == expected_target
        assert Path(self.bootstrap_env["MIND"]) == expected_mind
        return self.context

    async def develop(
        self, context: Any, goal: str, workflow: str, write: bool
    ) -> tuple[bool, str]:
        assert context is self.context
        self.develop_env = {k: self.env.get(k, "") for k in ("REPO_PATH", "MIND")}
        self.develop_calls.append((goal, workflow, write))
        if self.readiness_reason is not None:
            # what develop_from_goal returns after the Worker recorded
            # post_unavailable (Unit 3): the stable prefix, never a phase error
            from will.autonomy.autonomous_developer import UNAVAILABLE_PREFIX

            return (False, f"{UNAVAILABLE_PREFIX}{self.readiness_reason} (run_id=r)")
        return (self.develop_ok, "fake run")


# --- 1. in-process, deterministic --------------------------------------------


def test_happy_path_binds_materializes_and_invokes(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    before = subject_fingerprint(subject)
    evidence = tmp_path / "evidence"
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Fakes(env)

    code = execute(
        _opts(subject, evidence),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )

    assert code == EXIT_RAN
    runs = list((evidence / "runs").iterdir())
    assert len(runs) == 1
    run = runs[0]
    target, ev = run / "target", run / "evidence"
    assert target.is_dir() and ev.is_dir(), "execution copy and evidence are siblings"
    assert verify_floor(target / ".intent").clean
    assert (target / ".intent" / "workers" / "proposal_consumer_worker.yaml").is_file()
    assert env["REPO_PATH"] == str(target) and env["MIND"] == str(target / ".intent")
    assert fakes.develop_calls == [("Evaluate the package", "code_modification", False)]
    tb = fakes.context.target_binding
    assert tb is not None, "the binding is attached to the context for the Worker"
    assert tb.bound_repo_path == str(target) and tb.subject_path == str(subject)
    assert len(tb.bound_sha) == 40 and tb.displaced == ()
    assert tb.seed_hash == "5" * 64
    assert "QDRANT_URL" not in env
    binding = json.loads((ev / "binding.json").read_text())
    assert binding["bound_repo_path"] == str(target)
    assert binding["subject_fingerprint_before"] == before
    assert len(binding["subject_sha"]) == 40
    assert len(binding["bound_sha"]) == 40 and len(binding["bound_tree_hash"]) == 40
    assert (target / ".git").is_dir(), "the copy has its own fresh history"
    assert binding["collisions_displaced"] == []
    outcome = json.loads((ev / "outcome.json").read_text())
    assert outcome == {"outcome": "RAN", "message": "fake run", "stage": "develop"}
    assert subject_fingerprint(subject) == before, "the frozen subject is untouched"
    assert not (subject / "evidence").exists()


def test_unavailable_is_explicit_not_a_generic_failure(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Fakes(
        env, readiness_reason="no cognitive-role client for planner role 'planner'"
    )
    code = execute(
        _opts(subject, tmp_path / "evidence"),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_UNAVAILABLE
    assert len(fakes.develop_calls) == 1, (
        "the Worker is what records unavailability; the route does not pre-empt it"
    )
    run = next((tmp_path / "evidence" / "runs").iterdir())
    outcome = json.loads((run / "evidence" / "outcome.json").read_text())
    assert outcome["outcome"] == "UNAVAILABLE"
    assert outcome["stage"] == "develop"
    assert "planner" in outcome["message"]


def test_floor_wins_on_a_subject_with_colliding_intent(tmp_path: Path) -> None:
    subject = _subject(tmp_path, with_intent=True)
    (subject / ".intent" / "META").mkdir()
    (subject / ".intent" / "META" / "vocabulary.json").write_text('{"old": 1}\n')
    _git(["add", "-A"], subject)
    _git(["commit", "-q", "-m", "old law"], subject)
    before = subject_fingerprint(subject)
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Fakes(env)
    code = execute(
        _opts(subject, tmp_path / "evidence"),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_RAN
    run = next((tmp_path / "evidence" / "runs").iterdir())
    binding = json.loads((run / "evidence" / "binding.json").read_text())
    assert binding["collisions_displaced"] == ["META/vocabulary.json"]
    assert [d.path for d in fakes.context.target_binding.displaced] == [
        "META/vocabulary.json"
    ]
    manifest = json.loads((run / "evidence" / "collision_manifest.json").read_text())
    assert [d["path"] for d in manifest["displaced"]] == ["META/vocabulary.json"]
    assert (
        run / "evidence" / "displaced" / "META" / "vocabulary.json"
    ).read_text() == '{"old": 1}\n'
    assert verify_floor(run / "target" / ".intent").clean
    assert (
        run / "target" / ".intent" / "rules" / "code" / "subject_rule.json"
    ).is_file()
    assert subject_fingerprint(subject) == before


@pytest.mark.parametrize(
    "case",
    [
        "no_evidence_root",
        "evidence_inside_subject",
        "evidence_inside_core",
        "no_git",
        "no_database_url",
    ],
)
def test_pre_bootstrap_refusals(tmp_path: Path, case: str) -> None:
    subject = _subject(tmp_path)
    evidence: Path | None = tmp_path / "evidence"
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    if case == "no_evidence_root":
        evidence = None
    elif case == "evidence_inside_subject":
        evidence = subject / "ev"
    elif case == "evidence_inside_core":
        evidence = REPO_ROOT / "var" / "tmp" / "ev"
    elif case == "no_git":
        shutil.rmtree(subject / ".git")
    elif case == "no_database_url":
        env = {}
    fakes = _Fakes(env)
    code = execute(
        _opts(subject, evidence),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_BINDING_REFUSED
    assert fakes.develop_calls == []


def test_overlay_colliding_with_subject_law_is_refused(tmp_path: Path) -> None:
    subject = _subject(tmp_path, with_intent=True)
    overlay = tmp_path / "overlay"
    shutil.copytree(OVERLAY_DIR, overlay, ignore=shutil.ignore_patterns("__pycache__"))
    (overlay / "rules" / "code" / "subject_rule.json").write_text("{}\n")
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Fakes(env)
    code = execute(
        _opts(subject, tmp_path / "evidence", overlay),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_BINDING_REFUSED
    assert fakes.develop_calls == []


def test_missing_envelope_in_copy_is_refused_at_bind_time(tmp_path: Path) -> None:
    """#903 bind-time close: an overlay without the D-a envelope file yields
    a copy whose envelope cannot load -> refuse before bootstrap."""
    subject = _subject(tmp_path)
    overlay = tmp_path / "overlay"
    shutil.copytree(OVERLAY_DIR, overlay, ignore=shutil.ignore_patterns("__pycache__"))
    (overlay / "enforcement" / "config" / "safe_auto_approval_envelope.yaml").unlink()
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Fakes(env)
    code = execute(
        _opts(subject, tmp_path / "evidence", overlay),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_BINDING_REFUSED
    assert fakes.bootstrap_env == {}, "refused before bootstrap"
    run = next((tmp_path / "evidence" / "runs").iterdir())
    refusal = json.loads((run / "evidence" / "refusal.json").read_text())
    assert "safe_auto_approval_envelope" in refusal["reason"]


def test_floor_modified_in_copy_is_refused(tmp_path: Path, monkeypatch) -> None:
    import cli.runtime_external_run as route_mod
    from shared.infrastructure.intent import machinery_floor_integrity as mfi

    dirty = mfi.FloorIntegrityReport(ok=(), modified=("META/enums.json",), missing=())
    monkeypatch.setattr(mfi, "verify_floor", lambda _root: dirty)
    subject = _subject(tmp_path)
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Fakes(env)
    code = route_mod.execute(
        _opts(subject, tmp_path / "evidence"),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_BINDING_REFUSED
    assert fakes.develop_calls == []


def test_subject_changed_during_run_is_internal_failure(tmp_path: Path) -> None:
    subject = _subject(tmp_path)

    class _Tamper(_Fakes):
        async def develop(
            self, context: Any, goal: str, workflow: str, write: bool
        ) -> tuple[bool, str]:
            (subject / "package" / "mod.py").write_text("x = 2\n")
            return (True, "tampered")

    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Tamper(env)
    code = execute(
        _opts(subject, tmp_path / "evidence"),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_INTERNAL_FAILURE
    run = next((tmp_path / "evidence" / "runs").iterdir())
    assert (run / "evidence" / "subject_changed.json").is_file()


def test_legacy_direct_write_guard() -> None:
    guard_legacy_direct_write()
    guard_legacy_direct_write(legacy_direct_write=False)
    with pytest.raises(Exception, match="legacy_direct_write"):
        guard_legacy_direct_write(legacy_direct_write=True)


def test_route_source_never_passes_legacy_direct_write() -> None:
    src = (REPO_ROOT / "src" / "cli" / "runtime_external_run.py").read_text(
        encoding="utf-8"
    )
    # the only occurrences are the guard's own docstring/refusal text
    for line in src.splitlines():
        if "legacy_direct_write=True" in line:
            assert "refuse" in line.lower() or line.strip().startswith(
                ("#", '"', "'")
            ), line
    assert "develop_from_goal(" in src


def test_missing_seed_is_refused_before_bootstrap(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Fakes(env)
    code = execute(
        _opts(subject, tmp_path / "evidence", seed=None),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_BINDING_REFUSED
    assert fakes.bootstrap_env == {} and fakes.develop_calls == []


def test_qdrant_url_is_removed_from_the_bound_environment(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    env = {
        "DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db",
        "QDRANT_URL": "http://cores-own-vectors:6333",
    }
    fakes = _Fakes(env)
    code = execute(
        _opts(subject, tmp_path / "evidence"),
        core_repo_root=REPO_ROOT,
        environ=env,
        bootstrap=fakes.bootstrap,
        seed_environment=fakes.seed_environment,
        cognitive_init=fakes.cognitive_init,
        develop=fakes.develop,
    )
    assert code == EXIT_RAN
    assert "QDRANT_URL" not in env


def test_runner_prompt_is_installed_into_the_copy(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    env = {"DATABASE_URL": "postgresql://x:y@127.0.0.1:1/db"}
    fakes = _Fakes(env)
    assert (
        execute(
            _opts(subject, tmp_path / "evidence"),
            core_repo_root=REPO_ROOT,
            environ=env,
            bootstrap=fakes.bootstrap,
            seed_environment=fakes.seed_environment,
            cognitive_init=fakes.cognitive_init,
            develop=fakes.develop,
        )
        == EXIT_RAN
    )
    run = next((tmp_path / "evidence" / "runs").iterdir())
    installed = run / "target" / "var" / "prompts" / "plan_goal" / "model.yaml"
    assert (
        installed.read_bytes()
        == (REPO_ROOT / "var" / "prompts" / "plan_goal" / "model.yaml").read_bytes()
    )
    assert (run / "evidence" / "prompt_collision_manifest.json").is_file()


# --- 2. child-process: real entry point, early dispatch ------------------------


def _core_admin() -> list[str]:
    exe = shutil.which("core-admin")
    if exe:
        return [exe]
    return [sys.executable, "-m", "cli.admin_cli"]


def test_matches_route_is_exact() -> None:
    assert matches_route(["runtime", "external-run", "--subject", "x"])
    assert not matches_route(["runtime", "external-verify", "--target", "x"])
    assert not matches_route(["runtime"])


@pytest.mark.integration
def test_child_process_refuses_without_evidence_root(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("CORE_EVIDENCE_DIR", "REPO_PATH", "MIND")
    }
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    completed = subprocess.run(
        [
            *_core_admin(),
            "runtime",
            "external-run",
            "--subject",
            str(subject),
            "--goal",
            "g",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == EXIT_BINDING_REFUSED, completed.stderr[-2000:]
    assert "no evidence root" in completed.stderr
    assert not (tmp_path / "evidence").exists()


@pytest.mark.integration
def test_child_process_refuses_evidence_root_inside_core(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    env = {k: v for k, v in os.environ.items() if k not in ("REPO_PATH", "MIND")}
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["CORE_EVIDENCE_DIR"] = str(REPO_ROOT / "var" / "tmp" / "ev")
    completed = subprocess.run(
        [
            *_core_admin(),
            "runtime",
            "external-run",
            "--subject",
            str(subject),
            "--goal",
            "g",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == EXIT_BINDING_REFUSED, completed.stderr[-2000:]
    assert "CORE's checkout" in completed.stderr


# --- 3. live (opt-in) -----------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("CORE_EXTERNAL_RUN_LIVE") != "1",
    reason="live external run needs Docker + a reachable LLM; opt in with CORE_EXTERNAL_RUN_LIVE=1",
)
def test_live_external_run_against_disposable_database(tmp_path: Path) -> None:
    """Real entry point, real bootstrap against a disposable schema-only
    Postgres. Expected outcome today: UNAVAILABLE (no cognitive roles seeded
    -- the next blocking unit), with binding.json and outcome.json written
    and the subject untouched. RAN is accepted if roles happen to be seeded."""
    sys.path.insert(0, str(_HERE))
    from db_provisioning import (  # type: ignore[import-not-found]
        start_disposable_database,
        stop_disposable_database,
    )

    subject = _subject(tmp_path)
    before = subject_fingerprint(subject)
    db = start_disposable_database()
    try:
        env = {k: v for k, v in os.environ.items() if k not in ("REPO_PATH", "MIND")}
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["CORE_EVIDENCE_DIR"] = str(tmp_path / "evidence")
        env["DATABASE_URL"] = db.database_url
        completed = subprocess.run(
            [
                *_core_admin(),
                "runtime",
                "external-run",
                "--subject",
                str(subject),
                "--goal",
                "Evaluate the package",
                "--overlay",
                str(OVERLAY_DIR),
                "--seed",
                str(SEED_DIR),
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        # Unit 3 proof, while the disposable DB is still up: the Blackboard
        # on the isolated database carries the run's identity WITH the
        # binding, and `export-run` bound to the copy reconstructs it.
        run = next((tmp_path / "evidence" / "runs").iterdir())
        outcome = json.loads((run / "evidence" / "outcome.json").read_text())
        run_id = outcome["message"].rsplit("run_id=", 1)[-1].rstrip(")")
        export_env = dict(env)
        export_env["REPO_PATH"] = str(run / "target")
        export_env["MIND"] = str(run / "target" / ".intent")
        exported = subprocess.run(
            [*_core_admin(), "workers", "export-run", run_id, "--stdout"],
            cwd=REPO_ROOT,
            env=export_env,
            capture_output=True,
            text=True,
            timeout=300,
        )
    finally:
        stop_disposable_database(db)
    assert completed.returncode in (EXIT_RAN, EXIT_UNAVAILABLE), completed.stderr[
        -3000:
    ]
    assert (run / "evidence" / "binding.json").is_file()
    assert outcome["outcome"] in ("RAN", "UNAVAILABLE")
    assert subject_fingerprint(subject) == before
    assert exported.returncode == 0, exported.stderr[-3000:]
    doc = json.loads(exported.stdout.splitlines()[-1])
    assert doc["run_id"] == run_id
    assert doc["completeness"] == "complete", (
        "the unavailable outcome IS the terminal entry"
    )
    tb = doc["target_binding"]
    assert tb is not None
    binding = json.loads((run / "evidence" / "binding.json").read_text())
    assert tb["subject_sha"] == binding["subject_sha"]
    assert tb["bound_tree_hash"] == binding["bound_tree_hash"]
    assert tb["floor_hash"] == binding["floor_hash"]
    assert tb["overlay_hash"] == binding["overlay_hash"]
    subjects = [e["subject"] for e in doc["entries"]]
    assert f"goal_run.{run_id}.start" in subjects
    assert f"goal_run.{run_id}.outcome" in subjects
    if outcome["outcome"] == "UNAVAILABLE":
        outcome_entry = next(
            e for e in doc["entries"] if e["subject"].endswith(".outcome")
        )
        assert outcome_entry["payload"]["instrument_result"] == "unavailable"
