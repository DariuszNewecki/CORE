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
7. attach the binding facts (``TargetBinding``) to the context so
   ``GoalExecutionWorker`` records them in ``goal_run.<run_id>.start``; the
   Worker also probes planner readiness itself and records an explicit
   *unavailable* outcome on the Blackboard (``post_unavailable``) -- the
   route never impersonates a Worker; it maps the shim's stable
   ``UNAVAILABLE: `` message to exit code 4 and mirrors it in
   ``<run>/evidence/outcome.json``;
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
from ``schema.sql`` carries no cognitive-role assignments, so the Worker
will record ``unavailable`` until role/resource/prompt seeding lands (the
next blocking unit).
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import hashlib
import os
import subprocess
import uuid
from collections.abc import Awaitable, Callable, Mapping
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

# #895 U2/U3: `evaluation` is the read-only investigation workflow (Document A
# "governed evaluation"); without it here the route could not run it.
_WORKFLOW_TYPES = (
    "refactor_modularity",
    "code_modification",
    "coverage_remediation",
    "evaluation",
)


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
    seed: Path | None
    evidence_dir: Path | None
    write: bool
    probes: bool = False
    allowed_hosts: tuple[str, ...] = ()


class _Refused(Exception):
    """A refusal with an exit code and, optionally, structured evidence.

    ``evidence`` (when given) is written to ``outcome.json`` next to the
    plain ``refusal.json`` so a ruled refusal shape -- e.g. the egress
    preflight's ``{stage, rejected, allowed_hosts, reason}`` -- reaches the
    export without special-casing any one refusal at the handler.
    """

    def __init__(
        self,
        message: str,
        code: int = EXIT_BINDING_REFUSED,
        *,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = evidence


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
        "--seed",
        default=None,
        help=(
            "Seed directory (llm_resources/*.yaml, assignments.yaml, "
            "system_config.yaml) applied to the isolated database; required"
        ),
    )
    parser.add_argument(
        "--evidence-dir",
        default=None,
        help="Evidence root (else CORE_EVIDENCE_DIR); must be outside the subject and CORE",
    )
    parser.add_argument(
        "--write", action="store_true", help="Create a proposal (default: plan only)"
    )
    parser.add_argument(
        "--probes",
        action="store_true",
        help=(
            "#895 U3: run the ADR-159 apparatus-integrity probes I-5 (write "
            "containment) and I-6 (safe auto-approval envelope) in the bound "
            "process right after the run's start record; a failed probe ends "
            "the run with outcome APPARATUS_INTEGRITY_FAILED (exit 2)"
        ),
    )
    parser.add_argument(
        "--allowed-hosts",
        action="append",
        default=None,
        metavar="HOST[:PORT][,HOST[:PORT]...]",
        help=(
            "#895 U3 (ADR-159 §C): every endpoint the run is configured to reach "
            "(seeded LLM api_url, DATABASE_URL host, vector store) must be in this "
            "set, checked BEFORE seeding and reconciled after; a host outside it "
            "refuses the run (exit 2, stage preflight.egress). Repeatable or "
            "comma-separated. Omitted: recorded, not enforced."
        ),
    )
    ns = parser.parse_args(argv[2:])
    from shared.infrastructure.intent.external_run_egress import parse_allowed_hosts

    return ExternalRunOptions(
        subject=Path(ns.subject),
        goal=ns.goal,
        workflow_type=ns.workflow,
        overlay=Path(ns.overlay) if ns.overlay else None,
        seed=Path(ns.seed) if ns.seed else None,
        evidence_dir=Path(ns.evidence_dir) if ns.evidence_dir else None,
        write=bool(ns.write),
        probes=bool(ns.probes),
        allowed_hosts=parse_allowed_hosts(ns.allowed_hosts),
    )


def _write_evidence(evidence_root: Path, name: str, payload: dict[str, Any]) -> None:
    # Evidence tree only -- never the execution copy, never the subject. The
    # write itself lives with the other evidence-root writes (see
    # target_intent_assembly's module docstring for the write authority).
    from shared.infrastructure.intent.target_intent_assembly import write_evidence_json

    write_evidence_json(evidence_root, name, payload)


def _egress_preflight(
    opts: ExternalRunOptions, env: Mapping[str, str], evidence_root: Path
) -> dict[str, Any]:
    """Check every configured destination BEFORE the first egress (seeding).

    Reads the seed documents and the environment only -- nothing has been
    contacted yet. Writes ``egress.json`` and raises a structured
    ``_Refused`` (exit 2, ``stage: preflight.egress``) on the first host
    outside ``--allowed-hosts``. With no allowed set the destinations are
    recorded and nothing is enforced.
    """
    from shared.infrastructure.intent.external_run_egress import (
        configured_endpoints,
        rejected_endpoints,
    )
    from shared.infrastructure.intent.external_run_seed import (
        SeedError,
        load_seed_document,
    )

    try:
        seed = load_seed_document(opts.seed)  # type: ignore[arg-type]
    except SeedError as exc:
        raise _Refused(f"seed document refused: {exc}")
    endpoints = configured_endpoints(
        seed.resources,
        database_url=env.get("DATABASE_URL"),
        qdrant_url=env.get("QDRANT_URL"),
    )
    enforced = bool(opts.allowed_hosts)
    record: dict[str, Any] = {
        "allowed_hosts": list(opts.allowed_hosts),
        "enforcement": "enforced" if enforced else "not_requested",
        "preflight": [e.to_payload() for e in endpoints],
        "reconciled": None,
        "observation_ceiling": (
            "configured destinations only; socket-level egress is the "
            "coldroom's evidence, not the runner's"
        ),
    }
    _write_evidence(evidence_root, "egress.json", record)
    if enforced:
        rejected = rejected_endpoints(endpoints, opts.allowed_hosts)
        if rejected:
            _refuse_egress(rejected, opts, "preflight.egress")
    return record


async def _egress_reconcile(
    opts: ExternalRunOptions,
    env: Mapping[str, str],
    evidence_root: Path,
    record: dict[str, Any],
    registered_resources: Callable[[], Awaitable[list[dict[str, Any]]]],
) -> None:
    """After seeding: the endpoints actually registered in the isolated
    database must still be inside the allowed set (a seed document is the
    operator's declaration; the rows are what CORE will use). Only when
    enforcement was requested; a run without --allowed-hosts records its
    preflight set and touches nothing more. A reader failure refuses --
    an unverifiable endpoint set is never assumed allowed."""
    from shared.infrastructure.intent.external_run_egress import (
        configured_endpoints,
        rejected_endpoints,
    )

    if not opts.allowed_hosts:
        record["reconciled"] = "not_requested"
        _write_evidence(evidence_root, "egress.json", record)
        return
    try:
        registered = await registered_resources()
    except Exception as exc:
        raise _Refused(
            f"egress reconcile could not read the registered endpoints: {exc}",
            EXIT_BINDING_REFUSED,
            evidence={
                "stage": "preflight.egress.reconcile",
                "rejected_host": None,
                "rejected_port": None,
                "rejected": [],
                "allowed_hosts": list(opts.allowed_hosts),
                "reason": "registered endpoints unverifiable; not assumed allowed",
            },
        )
    endpoints = configured_endpoints(
        registered,
        database_url=env.get("DATABASE_URL"),
        qdrant_url=env.get("QDRANT_URL"),
    )
    record["reconciled"] = [e.to_payload() for e in endpoints]
    _write_evidence(evidence_root, "egress.json", record)
    rejected = rejected_endpoints(endpoints, opts.allowed_hosts)
    if rejected:
        _refuse_egress(rejected, opts, "preflight.egress.reconcile")


async def _registered_llm_resources() -> list[dict[str, Any]]:
    """``name``/``api_url`` of every row in the isolated ``core.llm_resources``."""
    from sqlalchemy import select

    from body.services.service_registry import service_registry
    from shared.infrastructure.database.models.operations import LlmResource

    async with service_registry.session() as session:
        rows = (
            await session.execute(select(LlmResource.name, LlmResource.api_url))
        ).all()
    return [{"name": name, "api_url": api_url} for name, api_url in rows]


def _refuse_egress(rejected: list[Any], opts: ExternalRunOptions, stage: str) -> None:
    first = rejected[0]
    hosts = ", ".join(f"{e.host}:{e.port}" if e.port else str(e.host) for e in rejected)
    raise _Refused(
        f"egress refused at {stage}: {hosts} not in --allowed-hosts "
        f"({', '.join(opts.allowed_hosts) or '<empty>'})",
        EXIT_BINDING_REFUSED,
        evidence={
            "stage": stage,
            "rejected_host": first.host,
            "rejected_port": first.port,
            "rejected": [e.to_payload() for e in rejected],
            "allowed_hosts": list(opts.allowed_hosts),
            "reason": (
                "ADR-159 §C: the runner may only be configured to reach hosts the "
                "operator allowed; checked before the first egress (seeding) and "
                "reconciled against the registered endpoints after it"
            ),
        },
    )


def _git_lines(path: Path, *args: str) -> list[str] | None:
    out = _git_read(path, *args)
    return None if out is None else [line for line in out.splitlines() if line]


# ID: 6a5f0707-7229-4989-9825-b204cb4782bc
def _write_inventory(
    subject: Path,
    subject_sha: str,
    copy: Any,
    copy_sha: str,
    evidence_root: Path,
    fingerprint_before: str,
) -> None:
    """``write_inventory.json`` (#895 U3, I-2): what was written where.

    Three distinct sections -- the frozen subject (must show nothing), the
    bound execution copy (``git status --porcelain`` plus
    ``git diff --name-status <bound_sha>``; FileHandler keeps no write log,
    the copy's own git history is the record) and the evidence directory
    (every file, this inventory listed explicitly since it is written last).
    Written on every exit from the run, refusal paths included.
    """
    from shared.infrastructure.intent.target_intent_assembly import subject_fingerprint

    evidence_files = sorted(
        str(p.relative_to(evidence_root))
        for p in evidence_root.rglob("*")
        if p.is_file()
    )
    if "write_inventory.json" not in evidence_files:
        evidence_files.append("write_inventory.json")
        evidence_files.sort()
    _write_evidence(
        evidence_root,
        "write_inventory.json",
        {
            "self": "write_inventory.json",
            "recorded_at": datetime.now(UTC).isoformat(),
            "subject": {
                "path": str(subject),
                "sha": subject_sha,
                "fingerprint_before": fingerprint_before,
                "fingerprint_after": subject_fingerprint(subject),
                "status_porcelain": _git_lines(subject, "status", "--porcelain"),
            },
            "copy": {
                "path": str(copy.target_root),
                "bound_sha": copy_sha,
                "status_porcelain": _git_lines(
                    copy.target_root, "status", "--porcelain"
                ),
                "diff_name_status_vs_bound_sha": _git_lines(
                    copy.target_root, "diff", "--name-status", copy_sha
                ),
            },
            "evidence_dir": {"path": str(evidence_root), "files": evidence_files},
        },
    )


# Ruling C (2026-09-15): the value QDRANT_URL is bound to for an external run.
# Empty, not absent -- see step 2b in :func:`execute` for why deletion leaks.
QDRANT_URL_UNBOUND = ""


# ID: 095ec12b-fa88-4b65-9ceb-eb178160aa88
def vector_store_leak(
    *, settings_qdrant_url: str | None, service_registry_qdrant_url: str | None
) -> str | None:
    """Ruling C proof, evaluated on the bound process AFTER Settings was born:
    neither the bound ``Settings`` nor the service registry may carry a
    policy-vector-store URL. Returns the refusal text, or ``None`` when the
    run is honestly without one. Pure; the bootstrap calls it with the live
    values so a future change to the dotenv cascade fails here, loudly,
    instead of quietly re-admitting CORE's own vectors."""
    carriers = [
        name
        for name, value in (
            ("Settings.QDRANT_URL", settings_qdrant_url),
            ("service_registry.qdrant_url", service_registry_qdrant_url),
        )
        if value
    ]
    if not carriers:
        return None
    return (
        "ruling C violated: the bound process carries a policy-vector-store URL "
        f"({', '.join(carriers)}); an external run has no target-bound vector "
        "store and must not reach CORE's own"
    )


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
    leak = vector_store_leak(
        settings_qdrant_url=settings.QDRANT_URL,
        service_registry_qdrant_url=service_registry.qdrant_url,
    )
    if leak is not None:
        raise _Refused(leak, EXIT_INTERNAL_FAILURE)
    envelope = load_safe_auto_approval_envelope()
    if envelope.get("_error"):
        raise _Refused(
            "safe-auto-approval envelope does not load through the bound "
            f"IntentRepository: {envelope.get('reason')}"
        )
    return core_context


async def _default_cognitive_init(core_context: Any) -> None:
    """Initialize the cognitive service AFTER the isolated database is seeded
    (it loads roles/resources/assignments once, on first initialize)."""
    from body.services.service_registry import service_registry

    cognitive = await service_registry.get_cognitive_service()
    async with service_registry.session() as session:
        await cognitive.initialize(session)
    core_context.cognitive_service = cognitive


# Ruling B (runner's prompt wins on collision) read at its principle: the
# prompt artifacts are runner machinery, so the copy carries the runner's
# WHOLE set, not a hand-kept list. Each seeded live run had grown the list
# by one (plan_goal; then planner_agent via PathResolver.prompt(); then the
# coder's code_generation_task_step_prompt and test_gen_prompt) -- a run
# reaching a new phase would keep finding the next one. Governor ruling
# 2026-09-15: the complete corpus, artifact directories and loose files
# alike. Every file is hashed into the seed manifest, so the identity stays
# exact. The planner's own ids remain named for the readiness probe.
PLANNER_PROMPT_IDS: tuple[str, ...] = ("plan_goal", "planner_agent")


# ID: 3f5c41d2-b812-44cf-946c-54307598a6d4
def runner_prompt_sources(core_repo_root: Path) -> dict[str, Path]:
    """``{prompt_id: <runner path>}`` for the COMPLETE prompt corpus under
    the runner's own prompt root (PathResolver, never a literal): every
    PromptModel artifact directory (``model.yaml`` present) and every loose
    prompt file at the root (the pre-PromptModel form the alignment
    specialists still load). The planner's ids must be among them."""
    from shared.path_resolver import PathResolver

    prompts_dir = PathResolver(core_repo_root).prompts_dir
    sources = {
        entry.name: entry
        for entry in sorted(prompts_dir.iterdir())
        if (entry.is_dir() and (entry / "model.yaml").is_file())
        or (entry.is_file() and not entry.name.startswith("."))
    }
    missing = [pid for pid in PLANNER_PROMPT_IDS if pid not in sources]
    if missing:
        raise _Refused(
            f"runner prompt root {prompts_dir} lacks the planner artifacts {missing}"
        )
    return sources


async def _default_seed_environment(
    core_context: Any,
    seed_dir: Path,
    database_url: str,
    copy: Any,
    evidence_root: Path,
) -> str:
    """Rulings A/D/E, in order: roles from the copy's taxonomy
    (project.cognitive_roles), seed document checked against those roles,
    pinned digests verified at the pinned endpoint, resources/assignments/
    system_config written by seed.external_run_resources -- both actions via
    ActionExecutor. Returns the canonical seed_hash; writes
    evidence/seed_manifest.json. Raises _Refused on any refusal."""
    from urllib.parse import urlsplit

    from shared.infrastructure.intent.cognitive_roles import (
        load_cognitive_role_capabilities,
    )
    from shared.infrastructure.intent.external_run_seed import (
        SeedError,
        check_seed_serves_roles,
        load_seed_document,
        probe_ollama_digest,
        seed_hash,
        seed_manifest,
    )
    from shared.infrastructure.intent.target_intent_assembly import write_evidence_json

    executor = getattr(core_context, "action_executor", None)
    if executor is None:
        raise _Refused(
            "CoreContext has no action_executor after bootstrap", EXIT_INTERNAL_FAILURE
        )

    try:
        seed = load_seed_document(seed_dir)
    except SeedError as exc:
        raise _Refused(f"seed document refused: {exc}")

    # E: roles from the execution copy's own taxonomy (bound singleton).
    projection = await executor.execute("project.cognitive_roles", write=True)
    if not projection.ok:
        raise _Refused(f"role projection failed: {projection.data.get('error')}")
    taxonomy = load_cognitive_role_capabilities()
    needed_roles = {a["role"] for a in seed.assignments} | {"Planner"}
    missing = sorted(r for r in needed_roles if r not in taxonomy)
    if missing:
        raise _Refused(f"roles absent from the copy's taxonomy: {missing}")
    required = {r: taxonomy[r] for r in sorted(needed_roles)}
    try:
        check_seed_serves_roles(seed, required)
    except SeedError as exc:
        raise _Refused(f"seed cannot serve the run's roles: {exc}")

    # A: pinned digest verified against the pinned endpoint.
    verified: dict[str, str] = {}
    for resource in seed.resources:
        pinned = resource.get("model_digest")
        if not pinned:
            continue
        try:
            observed = probe_ollama_digest(resource["api_url"], resource["model_name"])
        except SeedError as exc:
            raise _Refused(str(exc))
        if observed is None:
            raise _Refused(
                f"model {resource['model_name']!r} is not present at {resource['api_url']}"
            )
        if not observed.startswith(pinned) and not pinned.startswith(observed):
            raise _Refused(
                f"digest mismatch for {resource['name']!r}: pinned {pinned}, "
                f"endpoint reports {observed}"
            )
        verified[resource["name"]] = observed

    # D: the one governed writer, isolated-database proof inside the action.
    expected_database = urlsplit(database_url).path.lstrip("/")
    seeded = await executor.execute(
        "seed.external_run_resources",
        write=True,
        seed=seed,
        expected_database=expected_database,
    )
    if not seeded.ok:
        raise _Refused(f"seeding refused: {seeded.data.get('error')}")

    from shared.infrastructure.intent.machinery_floor_integrity import floor_manifest

    manifest = seed_manifest(
        seed,
        verified_digests=verified,
        prompts=[
            {
                "id": p.prompt_id,
                "files": dict(sorted(p.files.items())),
                "displaced_subject_sha256": dict(
                    sorted(p.displaced_original_sha256.items())
                ),
            }
            for p in copy.prompts
        ],
        roles=[
            {
                "role": role,
                "taxonomy_sha256": floor_manifest().get(
                    "taxonomies/cognitive_roles.yaml"
                ),
                "created": role in (projection.data.get("created") or []),
            }
            for role in sorted(needed_roles)
        ],
    )
    write_evidence_json(evidence_root, "seed_manifest.json", manifest)
    return seed_hash(manifest)


async def _default_develop(
    core_context: Any,
    goal: str,
    workflow_type: str,
    write: bool,
    probes: bool = False,
) -> tuple[bool, str]:
    from will.autonomy.autonomous_developer import develop_from_goal

    # ADR-160 gate: default legacy_direct_write only. Never pass it.
    return await develop_from_goal(
        context=core_context,
        goal=goal,
        workflow_type=workflow_type,
        write=write,
        probes=probes,
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
    seed_environment: Callable[
        [Any, Path, str, Any, Path], Awaitable[str]
    ] = _default_seed_environment,
    cognitive_init: Callable[[Any], Awaitable[None]] = _default_cognitive_init,
    develop: Callable[
        [Any, str, str, bool, bool], Awaitable[tuple[bool, str]]
    ] = _default_develop,
    registered_resources: Callable[
        [], Awaitable[list[dict[str, Any]]]
    ] = _registered_llm_resources,
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

        if opts.seed is None:
            raise _Refused("no seed directory: pass --seed (rulings D/E, 2026-09-15)")
        # 2b. bind BEFORE the first `shared` import (see step 1). The copy does
        # not exist yet; Settings only records the paths. Ruling C: no
        # target-bound policy-vector store exists, so QDRANT_URL is bound to
        # the EMPTY STRING here -- not deleted. Settings' dotenv cascade
        # reloads CORE's own .env with override=True and restores only keys
        # the process had preset, so a deleted key would come back carrying
        # CORE's live vector store (the side channel this ruling closes);
        # a preset empty string survives the cascade and Settings normalizes
        # it to None. The bootstrap re-proves the absence (step 6) and the
        # Worker records the degradation on the run's identity.
        env["REPO_PATH"] = str(bound_target)
        env["MIND"] = str(bound_mind)
        env["QDRANT_URL"] = QDRANT_URL_UNBOUND

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
            copy = materialize_execution_copy(
                subject,
                run_root,
                opts.overlay,
                prompt_sources=runner_prompt_sources(core_repo_root),
            )
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
                # #895 U3 (I-1): the task statement's identity, so Document A
                # can check the runner planned against exactly this text.
                "task_statement_sha256": hashlib.sha256(
                    opts.goal.encode("utf-8")
                ).hexdigest(),
                "workflow_type": opts.workflow_type,
                "write": opts.write,
                "probes": opts.probes,
                "allowed_hosts": list(opts.allowed_hosts),
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

            # 6a. egress preflight (#895 U3, governor correction 1, 2026-09-16):
            # seeding is the first egress (the digest probe contacts the model
            # endpoint; the seed actions write the isolated database), so the
            # configured destinations are checked BEFORE it, from the seed
            # documents and the environment, and reconciled AFTER it against
            # what was actually registered. Host/port only -- never the URL.
            egress = _egress_preflight(opts, env, evidence_root)  # type: ignore[arg-type]

            # 6b. seed the isolated environment (rulings A/D/E): roles from the
            # copy's own taxonomy via project.cognitive_roles; resources,
            # assignments and system_config from the operator's seed document
            # via seed.external_run_resources; pinned digest verified against
            # the pinned endpoint. Both actions go through ActionExecutor.
            seed_hash_value = await seed_environment(
                core_context,
                opts.seed,  # type: ignore[arg-type]
                env["DATABASE_URL"],
                copy,
                evidence_root,  # type: ignore[arg-type]
            )
            await _egress_reconcile(
                opts,
                env,
                evidence_root,  # type: ignore[arg-type]
                egress,
                registered_resources,
            )
            await cognitive_init(core_context)

            # 7. attach the binding facts to the context. GoalExecutionWorker
            # spreads them into goal_run.<run_id>.start (Unit 3) -- the
            # Blackboard record, as distinct from the apparatus's binding.json.
            from shared.models.target_binding import DisplacedFile, TargetBinding

            core_context.target_binding = TargetBinding(
                subject_path=str(subject),
                subject_sha=subject_sha,
                subject_tree_hash=subject_tree,
                bound_repo_path=str(copy.target_root),
                bound_sha=copy_sha,
                bound_tree_hash=copy_tree,
                floor_hash=copy.floor_hash,
                overlay_hash=copy.overlay_hash,
                displaced=tuple(
                    DisplacedFile(
                        path=d.path,
                        original_sha256=d.original_sha256,
                        installed_floor_sha256=d.installed_floor_sha256,
                    )
                    for d in copy.displaced
                ),
                seed_hash=seed_hash_value,
            )

            # 8. the run (default legacy_direct_write; guard is the contract).
            # Readiness is the Worker's to probe and record (post_unavailable);
            # the route only maps its stable UNAVAILABLE_PREFIX to an exit code.
            guard_legacy_direct_write()
            ok, message = await develop(
                core_context, opts.goal, opts.workflow_type, opts.write, opts.probes
            )
            from will.autonomy.autonomous_developer import (
                APPARATUS_INTEGRITY_PREFIX,
                UNAVAILABLE_PREFIX,
            )

            # #895 U3: a failed I-5/I-6 probe is an apparatus-integrity refusal
            # (exit 2), recorded on the run identity by the Worker; distinct
            # from unavailability (4) and internal failure (64).
            if not ok and message.startswith(APPARATUS_INTEGRITY_PREFIX):
                _write_evidence(
                    evidence_root,  # type: ignore[arg-type]
                    "outcome.json",
                    {
                        "outcome": "APPARATUS_INTEGRITY_FAILED",
                        "message": message,
                        "stage": "probes",
                        "failed_probes": message.removeprefix(
                            APPARATUS_INTEGRITY_PREFIX
                        )
                        .split(" (run_id=")[0]
                        .split(", "),
                    },
                )
                _err_console.print(f"APPARATUS INTEGRITY FAILED — {message}")
                return EXIT_BINDING_REFUSED
            if not ok and message.startswith(UNAVAILABLE_PREFIX):
                _write_evidence(
                    evidence_root,  # type: ignore[arg-type]
                    "outcome.json",
                    {"outcome": "UNAVAILABLE", "message": message, "stage": "develop"},
                )
                _err_console.print(f"UNAVAILABLE — {message}")
                return EXIT_UNAVAILABLE
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

        inventory = functools.partial(
            _write_inventory, subject, subject_sha, copy, copy_sha, evidence_root
        )
        try:
            code = asyncio.run(_rest())
        finally:
            # 8b. #895 U3 (I-2): what was written where, recorded on every
            # exit from the run -- refusal paths included.
            inventory(fingerprint_before)

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
            if exc.evidence is not None:
                _write_evidence(
                    evidence_root,
                    "outcome.json",
                    {
                        "outcome": "REFUSED",
                        "code": exc.code,
                        "message": str(exc),
                        **exc.evidence,
                    },
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
