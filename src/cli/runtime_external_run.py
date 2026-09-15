# src/cli/runtime_external_run.py
"""
Pre-bootstrap dispatch and implementation for
``core-admin runtime external-run`` (#894, ADR-159 Note 2026-09-15:
one Mind per process, Condition 1 floor integrity, Condition 2 subject
isolation with the floor-wins collision rule).

Binds one CORE process to a **materialized execution copy** of a frozen
external subject and runs one goal-driven workflow against it:

    core-admin runtime external-run --subject <path> --goal "<text>"
        [--workflow <closed vocab>] [--overlay <dir>] [--evidence-dir <path>]
        [--write]

Order of operations -- fail closed at each step, nothing constructed before
its check passes:

1. resolve ``--subject``; require ``.git``; record its HEAD sha and a
   symlink-safe content fingerprint (``subject_fingerprint``);
2. resolve the evidence root (``--evidence-dir`` or ``CORE_EVIDENCE_DIR``;
   unset = refuse); it must lie outside the subject and outside CORE's own
   checkout; create ``<evidence>/runs/<run_dir>/``;
3. report floor collisions in the subject's ``.intent/`` (``find_collisions``,
   D-e) -- under the collision rule these are displaced, not refused;
4. materialize the execution copy: ``<run>/target/`` (subject + floor +
   overlay, originals preserved under ``<run>/evidence/displaced/`` with a
   deterministic manifest) and ``<run>/evidence/`` as siblings;
   the copy gets its own fresh git history (one baseline commit; its tree
   hash is Condition 2's "copy's tree hash"); ``verify_floor`` must be clean
   and the overlay-owned envelope must load from the copy;
5. ``validate_external_target_binding`` against the now-existing copy (the
   environment was bound to the copy's deterministic path in step 2, BEFORE
   the first ``shared`` import -- importing any ``shared`` module constructs
   ``Settings()``, which must be born already bound; ``DATABASE_URL`` is
   required from the environment);
6. bootstrap the ordinary ``CoreContext``; refuse on any root disagreement
   (``find_root_disagreements``); require the safe-auto-approval envelope to
   load from the copy's ``.intent/`` (a copy missing its overlay-owned
   envelope refuses here -- the bind-time close of #903's new entry);
7. readiness probe: the planner prompt and its cognitive-role client must
   be obtainable; if not, the outcome is an explicit ``UNAVAILABLE`` -- not a
   generic failure -- recorded in ``<run>/evidence/outcome.json``;
8. ``develop_from_goal(context, goal, workflow_type, write=write)`` with the
   DEFAULT ``legacy_direct_write`` (the route exposes no flag and refuses any
   value but False: ``dev refactor`` is a grandfathered opt-out and not a
   valid base; ADR-160 gate);
9. re-fingerprint the subject; any change is an ``INTERNAL_FAILURE``.

Same import-order discipline as ``cli.runtime_external_verify``: this
module is stdlib + Rich at module scope; every CORE import happens inside
:func:`execute` after the environment is bound. ``cli.admin_cli`` dispatches
here before its own heavy imports via :func:`matches_route`, an exact
two-token match -- not a general router.

Read-only git queries on the subject (``rev-parse HEAD``) run before any
CORE bootstrap, when ``GitService`` cannot be imported without initializing
the IntentRepository singleton against the wrong root; the one small
``subprocess`` call here is justified by that ordering constraint exactly as
``external_target_binding._git_toplevel`` documents, and mutates nothing.

Unit 2 delivers binding, materialization, refusals and invocation. It does
NOT claim the complete runner is operational: an isolated database seeded
from ``schema.sql`` carries no cognitive-role assignments, so step 7 will
report ``UNAVAILABLE`` until role/resource seeding lands (the next blocking
unit). Run identity carrying the binding facts is Unit 3.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console


ROUTE: tuple[str, str] = ("runtime", "external-run")

_RECURSION_GUARD_ENV = "CORE_EXTERNAL_RUN_ACTIVE"

_console = Console(width=4096)
_err_console = Console(stderr=True, width=4096)

# Exit codes mirror runtime_external_verify (defined locally for the same
# import-ordering reason); RAN and UNAVAILABLE are this route's additions.
EXIT_RAN = 0
EXIT_BINDING_REFUSED = 2
EXIT_UNAVAILABLE = 4
EXIT_INTERNAL_FAILURE = 64

_WORKFLOW_TYPES = ("refactor_modularity", "code_modification", "coverage_remediation")


# ID: c4d63597-1118-4232-afd5-84a60850ff3c
def matches_route(argv: list[str]) -> bool:
    """True iff *argv* (``sys.argv[1:]``) invokes ``runtime external-run``.
    Pure prefix match on the first two tokens -- no parsing, no imports."""
    return len(argv) >= 2 and tuple(argv[:2]) == ROUTE


@dataclass(frozen=True)
# ID: 48b8c4b5-ac6e-4d4b-babe-5d6c757881f6
class ExternalRunOptions:
    """Parsed, unresolved operator inputs for one external run."""

    subject: Path
    goal: str
    workflow_type: str
    overlay: Path | None
    evidence_dir: Path | None
    write: bool


class _Refused(Exception):
    def __init__(self, message: str, code: int = EXIT_BINDING_REFUSED) -> None:
        super().__init__(message)
        self.code = code


class _EnvironScope:
    """Restore a fixed set of environment variables on exit (mirrors
    runtime_external_verify)."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self._saved: dict[str, str | None] = {}

    def __enter__(self) -> _EnvironScope:
        for k in self._keys:
            self._saved[k] = os.environ.get(k)
        return self

    def __exit__(self, *exc_info: object) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _git_read(path: Path, *args: str) -> str | None:
    """Read-only ``git -C <path> <args>``; None on any failure. Never mutates."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_init_copy(target: Path) -> tuple[str, str]:
    """Give the execution copy its own fresh git history: one baseline commit
    of everything materialized (the subject's own ``.git`` was excluded).
    The bound runtime needs a repository (binding validator, pre/post SHAs
    for any proposal), and the baseline tree hash is Condition 2's "copy's
    tree hash". Writes only inside the copy, under the evidence root.
    Returns (baseline_sha, baseline_tree_hash)."""
    ident = [
        "-c",
        "user.email=external-run@core.local",
        "-c",
        "user.name=CORE external-run",
    ]
    subprocess.run(
        ["git", "-C", str(target), "init", "-q"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(target), *ident, "config", "commit.gpgsign", "false"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(target), *ident, "add", "-A"], check=True, capture_output=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(target),
            *ident,
            "commit",
            "-q",
            "-m",
            "external-run execution copy baseline",
        ],
        check=True,
        capture_output=True,
    )
    return (
        _git_read(target, "rev-parse", "HEAD") or "<unavailable>",
        _git_read(target, "write-tree") or "<unavailable>",
    )


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


# ID: a6054160-4330-4a8f-83b0-5ef7a2b15b60
def parse_args(argv: list[str]) -> ExternalRunOptions:
    parser = argparse.ArgumentParser(
        prog="core-admin runtime external-run",
        description=(
            "Bind this process to a materialized copy of an external subject "
            "repository and run one goal-driven workflow against it."
        ),
    )
    parser.add_argument(
        "--subject", required=True, help="Frozen subject repository (read-only)"
    )
    parser.add_argument("--goal", required=True, help="Free-text goal")
    parser.add_argument(
        "--workflow",
        default="code_modification",
        choices=_WORKFLOW_TYPES,
        help="Workflow type (closed vocabulary)",
    )
    parser.add_argument(
        "--overlay", default=None, help="Overlay directory mirroring .intent/ layout"
    )
    parser.add_argument(
        "--evidence-dir",
        default=None,
        help="Evidence root (else CORE_EVIDENCE_DIR); must be outside the subject and CORE",
    )
    parser.add_argument(
        "--write", action="store_true", help="Create a proposal (default: plan only)"
    )
    ns = parser.parse_args(argv[2:])
    return ExternalRunOptions(
        subject=Path(ns.subject),
        goal=ns.goal,
        workflow_type=ns.workflow,
        overlay=Path(ns.overlay) if ns.overlay else None,
        evidence_dir=Path(ns.evidence_dir) if ns.evidence_dir else None,
        write=bool(ns.write),
    )


def _write_evidence(evidence_root: Path, name: str, payload: dict[str, Any]) -> None:
    # Evidence tree only -- never the execution copy, never the subject. The
    # write itself lives with the other evidence-root writes (see
    # target_intent_assembly's module docstring for the write authority).
    from shared.infrastructure.intent.target_intent_assembly import write_evidence_json

    write_evidence_json(evidence_root, name, payload)


async def _default_bootstrap(expected_target: Path, expected_mind: Path) -> Any:
    """Construct the ordinary CoreContext against the bound environment and
    prove it is bound where we think: every runtime root must agree with
    the execution copy (``find_root_disagreements``, as external-verify
    does) and the safe-auto-approval envelope must load through the bound
    IntentRepository singleton. Initializes the cognitive service on one
    session. Raises ``_Refused`` on any disagreement; returns the context."""
    from body.infrastructure.bootstrap import create_core_context
    from body.services.service_registry import service_registry
    from cli.runtime_external_verify import find_root_disagreements
    from shared.config import settings
    from shared.infrastructure.bootstrap_registry import bootstrap_registry
    from shared.infrastructure.intent.action_risk import (
        load_safe_auto_approval_envelope,
    )
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    core_context = create_core_context(service_registry)
    disagreements = find_root_disagreements(
        git_service_repo_path=core_context.git_service.repo_path,
        settings_repo_path=settings.REPO_PATH,
        settings_mind=settings.MIND,
        bootstrap_registry_repo_path=bootstrap_registry.get_repo_path(),
        service_registry_repo_path=(
            Path(service_registry.repo_path)
            if service_registry.repo_path is not None
            else None
        ),
        intent_repository_root=get_intent_repository().root,
        expected_target=expected_target.resolve(),
        expected_mind=expected_mind.resolve(),
    )
    if disagreements:
        raise _Refused(
            "runtime roots disagree after bootstrap: " + "; ".join(disagreements),
            EXIT_INTERNAL_FAILURE,
        )
    envelope = load_safe_auto_approval_envelope()
    if envelope.get("_error"):
        raise _Refused(
            "safe-auto-approval envelope does not load through the bound "
            f"IntentRepository: {envelope.get('reason')}"
        )
    cognitive = await service_registry.get_cognitive_service()
    async with service_registry.session() as session:
        await cognitive.initialize(session)
    core_context.cognitive_service = cognitive
    return core_context


async def _default_readiness(core_context: Any) -> str | None:
    """Return a reason the run is UNAVAILABLE, or None when the planner's
    prompt and its cognitive-role client are both obtainable."""
    from shared.ai.prompt_model import PromptModel

    try:
        model = PromptModel.load("plan_goal")
    except Exception as exc:
        return f"planner prompt 'plan_goal' unavailable under the bound copy: {exc}"
    role = model._artifact.manifest.role
    try:
        await core_context.cognitive_service.aget_client_for_role(role)
    except Exception as exc:
        return f"no cognitive-role client for planner role {role!r} in the isolated database: {exc}"
    return None


async def _default_develop(
    core_context: Any, goal: str, workflow_type: str, write: bool
) -> tuple[bool, str]:
    from will.autonomy.autonomous_developer import develop_from_goal

    # ADR-160 gate: default legacy_direct_write only. Never pass it.
    return await develop_from_goal(
        context=core_context, goal=goal, workflow_type=workflow_type, write=write
    )


# ID: cf5ddcfc-6b26-4571-81bf-573f19f03c7d
def guard_legacy_direct_write(**kwargs: Any) -> None:
    """Refuse any attempt to route a legacy_direct_write=True call through
    this command. Load-bearing: the only existing CLI goal surface
    (``dev refactor``) is a grandfathered opt-out and is not a valid base."""
    if kwargs.get("legacy_direct_write", False):
        raise _Refused(
            "external-run refuses legacy_direct_write=True: external runs are "
            "proposal-gated (ADR-160; ADR-159 Note 2026-09-15)."
        )


# ID: 8015c49b-e00f-4ab8-bc55-b73d4508103b
def execute(
    opts: ExternalRunOptions,
    *,
    core_repo_root: Path,
    environ: dict[str, str] | None = None,
    bootstrap: Callable[[Path, Path], Awaitable[Any]] = _default_bootstrap,
    readiness: Callable[[Any], Awaitable[str | None]] = _default_readiness,
    develop: Callable[
        [Any, str, str, bool], Awaitable[tuple[bool, str]]
    ] = _default_develop,
) -> int:
    """Run the nine steps; return the exit code. Dependencies are injectable
    so the orchestration can be proven deterministically in-process; the
    real ones are the defaults."""
    env = os.environ if environ is None else environ
    core_repo_root = core_repo_root.resolve()
    evidence_root: Path | None = None
    try:
        # 1. subject (stdlib only -- nothing under `shared` may be imported
        # yet: importing ANY shared module constructs Settings(), and Settings
        # must be born already bound to the execution copy, exactly as
        # runtime_external_verify binds before its first CORE import).
        try:
            subject = opts.subject.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise _Refused(
                f"subject does not resolve to an existing path: {opts.subject} ({exc})"
            )
        if not (subject / ".git").exists():
            raise _Refused(f"no .git found at subject: {subject}")
        if _is_within(subject, core_repo_root) or _is_within(core_repo_root, subject):
            raise _Refused(f"subject overlaps CORE's own checkout: {subject}")
        subject_sha = _git_read(subject, "rev-parse", "HEAD") or "<unavailable>"
        subject_tree = _git_read(subject, "rev-parse", "HEAD^{tree}") or "<unavailable>"

        # 2. evidence root and the run directory (still stdlib only)
        raw_evidence = opts.evidence_dir or (
            Path(env["CORE_EVIDENCE_DIR"]) if env.get("CORE_EVIDENCE_DIR") else None
        )
        if raw_evidence is None:
            raise _Refused(
                "no evidence root: pass --evidence-dir or set CORE_EVIDENCE_DIR"
            )
        evidence_base = raw_evidence.expanduser().resolve()
        if _is_within(evidence_base, subject) or _is_within(subject, evidence_base):
            raise _Refused(
                f"evidence root {evidence_base} is inside (or contains) the subject"
            )
        if _is_within(evidence_base, core_repo_root) or _is_within(
            core_repo_root, evidence_base
        ):
            raise _Refused(
                f"evidence root {evidence_base} is inside (or contains) CORE's checkout"
            )
        run_dir_name = (
            f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        )
        run_root = evidence_base / "runs" / run_dir_name
        bound_target = run_root / "target"
        bound_mind = bound_target / ".intent"
        if not env.get("DATABASE_URL"):
            raise _Refused(
                "DATABASE_URL is not set: an external run needs its own isolated database"
            )

        # 2b. bind BEFORE the first `shared` import (see step 1). The copy does
        # not exist yet; Settings only records the paths.
        env["REPO_PATH"] = str(bound_target)
        env["MIND"] = str(bound_mind)

        from shared.infrastructure.external_target_binding import (
            ExternalTargetBindingError,
            validate_external_target_binding,
        )
        from shared.infrastructure.intent.action_risk import validate_envelope_file
        from shared.infrastructure.intent.machinery_floor_integrity import (
            find_collisions,
            verify_floor,
        )
        from shared.infrastructure.intent.target_intent_assembly import (
            OverlayCollisionError,
            SubjectCopyError,
            materialize_execution_copy,
            subject_fingerprint,
        )

        try:
            fingerprint_before = subject_fingerprint(subject)
        except SubjectCopyError as exc:
            raise _Refused(str(exc))

        # 3. collisions (informational under the floor-wins rule)
        collisions = find_collisions(subject / ".intent")

        # 4. materialize
        try:
            copy = materialize_execution_copy(subject, run_root, opts.overlay)
        except (OverlayCollisionError, SubjectCopyError, FileExistsError) as exc:
            raise _Refused(str(exc))
        evidence_root = copy.evidence_root
        try:
            copy_sha, copy_tree = _git_init_copy(copy.target_root)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise _Refused(
                f"could not initialize the execution copy's git history: {exc}",
                EXIT_INTERNAL_FAILURE,
            )
        report = verify_floor(copy.intent_root)
        if not report.clean:
            raise _Refused(f"floor integrity failed in the copy: {report.describe()}")
        # 4b. the overlay-owned envelope must load from the copy (bind-time
        # close of the one new entry into #903's window that Condition 1's
        # move created); re-checked through the bound singleton after bootstrap.
        envelope_check = validate_envelope_file(copy.intent_root)
        if envelope_check.get("_error"):
            raise _Refused(
                "safe-auto-approval envelope does not load from the copy's "
                f".intent/: {envelope_check.get('reason')}"
            )
        _write_evidence(
            evidence_root,
            "binding.json",
            {
                "subject": str(subject),
                "subject_sha": subject_sha,
                "subject_tree_hash": subject_tree,
                "subject_fingerprint_before": fingerprint_before,
                "bound_repo_path": str(copy.target_root),
                "bound_sha": copy_sha,
                "bound_tree_hash": copy_tree,
                "floor_hash": copy.floor_hash,
                "overlay_hash": copy.overlay_hash,
                "overlay_files": list(copy.overlay_files),
                "collisions_displaced": [d.path for d in copy.displaced],
                "goal": opts.goal,
                "workflow_type": opts.workflow_type,
                "write": opts.write,
            },
        )

        # 5. validate the binding against the now-existing copy (env bound in 2b)
        if (copy.target_root, copy.intent_root) != (bound_target, bound_mind):
            raise _Refused(
                "materialized copy is not at the bound path", EXIT_INTERNAL_FAILURE
            )
        try:
            validate_external_target_binding(
                copy.target_root,
                repo_path_value=env.get("REPO_PATH"),
                mind_value=env.get("MIND"),
                database_url_value=env.get("DATABASE_URL"),
                core_repo_root=core_repo_root,
            )
        except ExternalTargetBindingError as exc:
            raise _Refused(str(exc))

        # 6-9 need an event loop; defensive guard per async.no_manual_loop_run
        # (the CLI entry point is synchronous; a running loop here is a bug).
        try:
            running_loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop and running_loop.is_running():  # pragma: no cover
            raise _Refused(
                "external-run must not be invoked from a running event loop",
                EXIT_INTERNAL_FAILURE,
            )

        async def _rest() -> int:
            # 6. bootstrap against the bound copy; the bootstrap proves root
            # agreement and the envelope through the bound singleton itself.
            core_context = await bootstrap(copy.target_root, copy.intent_root)

            # 7. readiness -> explicit UNAVAILABLE
            reason = await readiness(core_context)
            if reason is not None:
                _write_evidence(
                    evidence_root,  # type: ignore[arg-type]
                    "outcome.json",
                    {"outcome": "UNAVAILABLE", "reason": reason, "stage": "readiness"},
                )
                _err_console.print(f"UNAVAILABLE — {reason}")
                return EXIT_UNAVAILABLE

            # 8. the run (default legacy_direct_write; guard is the contract)
            guard_legacy_direct_write()
            ok, message = await develop(
                core_context, opts.goal, opts.workflow_type, opts.write
            )
            _write_evidence(
                evidence_root,  # type: ignore[arg-type]
                "outcome.json",
                {
                    "outcome": "RAN" if ok else "FAILED",
                    "message": message,
                    "stage": "develop",
                },
            )
            _console.print(f"{'RAN' if ok else 'FAILED'} — {message}")
            return EXIT_RAN if ok else EXIT_INTERNAL_FAILURE

        code = asyncio.run(_rest())

        # 9. subject untouched?
        fingerprint_after = subject_fingerprint(subject)
        if fingerprint_after != fingerprint_before:
            _write_evidence(
                evidence_root,
                "subject_changed.json",
                {"before": fingerprint_before, "after": fingerprint_after},
            )
            raise _Refused(
                "subject fingerprint changed during the run", EXIT_INTERNAL_FAILURE
            )

        _console.print(f"Subject:        {subject} @ {subject_sha[:12]}")
        _console.print(f"Execution copy: {copy.target_root}")
        _console.print(f"Evidence:       {copy.evidence_root}")
        _console.print(
            f"Floor hash:     {copy.floor_hash[:16]}  displaced: {len(copy.displaced)}"
            + (f" ({', '.join(collisions)})" if collisions else "")
        )
        return code

    except _Refused as exc:
        if evidence_root is not None:
            _write_evidence(
                evidence_root, "refusal.json", {"code": exc.code, "reason": str(exc)}
            )
        _err_console.print(f"REFUSED — {exc}")
        return exc.code


# ID: 525fd339-ef8c-4454-a354-c4efc945c829
def run(argv: list[str]) -> int:
    """Entry point for the pre-bootstrap dispatch; *argv* is ``sys.argv[1:]``."""
    if os.environ.get(_RECURSION_GUARD_ENV):
        _err_console.print("REFUSED — recursive external-run invocation detected")
        return EXIT_BINDING_REFUSED
    with _EnvironScope([_RECURSION_GUARD_ENV, "REPO_PATH", "MIND"]):
        os.environ[_RECURSION_GUARD_ENV] = "1"
        opts = parse_args(argv)
        core_repo_root = Path(__file__).resolve().parents[2]
        try:
            return execute(opts, core_repo_root=core_repo_root)
        except Exception as exc:
            _err_console.print(f"INTERNAL FAILURE — {type(exc).__name__}: {exc}")
            return EXIT_INTERNAL_FAILURE
