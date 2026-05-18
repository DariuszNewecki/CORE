# src/will/governance/fix_runner.py

"""
Fix runner facade — Will-layer entry point for the /fix and /quality APIs
(ADR-055).

The API layer must not import body.* directly (architecture.api.no_body_bypass).
This module is the sanctioned bridge for the /fix and /quality surfaces:

* `list_registered_action_ids` / `list_registered_flow_ids` — synchronous
  helpers used at request time to validate `fix_id` / `flow_id` against
  their respective registries. Unknown ids must produce a 422, not a 500
  from a failed execution.

* `run_and_persist_fix` — fire-and-forget atomic-action execution path.
* `run_and_persist_flow` — fire-and-forget Flow execution path. Used by
  POST /fix/all (caller picks the flow_id and the row's `kind`).
* `run_and_persist_modularity` — fire-and-forget modularity remediation
  path. Bridges to the will.self_healing modularity service rather
  than a Flow YAML — there is no `flow.modularity` declaration.
* `bootstrap_ir` — synchronous IR (incident-response) scaffold writer
  for POST /fix/ir. Bypasses fix_runs — the operation is a one-shot
  filesystem write that completes inline.

* `run_quality_imports` / `run_quality_body_ui` — synchronous helpers
  for POST /quality/imports and POST /quality/body-ui. Return the
  inline ADR-055 D3 shape `{status, violations}` without touching
  fix_runs.
* `run_and_persist_quality` — fire-and-forget runner for POST
  /quality/lint, /quality/tests, /quality/system, /quality/gates. All
  four share the kind='quality_check' fix_runs row; the caller picks
  the per-check fix_id.

All async runners share `_update_fix_run_status` for the
pending → executing → completed/failed lifecycle. Persistence target
is core.fix_runs (ADR-055 D1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

from body.atomic.executor import ActionExecutor
from body.atomic.registry import action_registry
from body.flows.executor import FlowExecutor
from body.flows.registry import flow_registry
from shared.context import CoreContext
from shared.logger import getLogger


__all__ = [
    "bootstrap_ir",
    "list_action_definitions",
    "list_registered_action_ids",
    "list_registered_flow_ids",
    "run_and_persist_fix",
    "run_and_persist_flow",
    "run_and_persist_modularity",
    "run_and_persist_quality",
    "run_quality_body_ui",
    "run_quality_imports",
]


logger = getLogger(__name__)


_IR_DIR = Path(".intent") / "mind" / "ir"
_IR_FILES: dict[str, tuple[Path, str]] = {
    "triage": (
        _IR_DIR / "triage_log.yaml",
        'version: "0.1.0"\ntype: "incident_triage_log"\nentries: []\n',
    ),
    "log": (
        _IR_DIR / "incident_log.yaml",
        'version: "0.1.0"\ntype: "incident_response_log"\nentries: []\n',
    ),
}


# ID: ab1474e8-8ee7-45dc-b178-3b7daa4c94f2
def list_registered_action_ids() -> set[str]:
    """Return the set of atomic-action IDs currently in the registry.

    Importing body.atomic.executor triggers action registration as a
    side effect, so the registry is populated by the time this returns.
    Used by POST /fix/run/{fix_id} to reject unknown ids with 422.
    """
    import body.atomic  # noqa: F401 — triggers registration

    return {definition.action_id for definition in action_registry.list_all()}


# ID: d905c554-af70-49c5-85c3-82661d169fab
def list_action_definitions(category: str | None = None) -> list[dict]:
    """Return serialised ActionDefinition metadata for every registered action.

    When `category` is supplied, the list is filtered to that category
    (e.g. 'fix' for GET /fix/commands). The executor callable is
    intentionally omitted; the rest of the dataclass is flattened to
    JSON-safe primitives.
    """
    import body.atomic  # noqa: F401 — triggers registration

    definitions = action_registry.list_all()
    if category is not None:
        definitions = [d for d in definitions if d.category.value == category]

    return [
        {
            "action_id": d.action_id,
            "description": d.description,
            "category": d.category.value,
            "policies": list(d.policies),
            "impact_level": d.impact_level,
            "requires_db": d.requires_db,
            "requires_vectors": d.requires_vectors,
            "remediates": list(d.remediates),
        }
        for d in definitions
    ]


# ID: b4c3edef-3730-4812-8675-566cc60bfdbe
def list_registered_flow_ids() -> set[str]:
    """Return the set of flow IDs currently in the flow registry.

    flow_registry lazy-loads from .intent/flows/ on first access; no
    side-effect import is needed. Used by POST /fix/all and
    POST /fix/modularity to reject unknown flow ids with 422.
    """
    return {definition.flow_id for definition in flow_registry.list_all()}


# ID: cf0a9da9-553e-492c-ba14-ace0de6a62ae
async def _update_fix_run_status(
    session: Any,
    run_id: UUID,
    status: str,
    *,
    started: bool = False,
    finished: bool = False,
    error: str | None = None,
    result: dict | None = None,
) -> None:
    """Update a fix_runs row's lifecycle state.

    `started` sets started_at = now(); `finished` sets finished_at = now().
    `error` writes to the error column; `result` is JSON-serialised and
    written to the result jsonb column. Each call commits.
    """
    sets = ["status = :status"]
    params: dict[str, Any] = {"status": status, "rid": run_id}

    if started:
        sets.append("started_at = now()")
    if finished:
        sets.append("finished_at = now()")
    if error is not None:
        sets.append("error = :err")
        params["err"] = error
    if result is not None:
        sets.append("result = cast(:result as jsonb)")
        params["result"] = json.dumps(result, default=str)

    await session.execute(
        text(f"UPDATE core.fix_runs SET {', '.join(sets)} WHERE id = :rid"),
        params,
    )
    await session.commit()


# ID: 108ce306-3937-4138-a5ed-9ab2f11ed46d
async def run_and_persist_fix(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    fix_id: str,
    target_files: list[str] | None,
    write: bool,
    params: dict[str, Any] | None = None,
) -> None:
    """Execute an atomic fix and persist the result on the fix_runs row.

    The row has already been INSERTed by the route handler with
    status='pending' — this function transitions it through executing
    and into completed / failed.

    `params` carries action-specific kwargs (e.g. fix.docstrings's
    `limit`) — merged into the execute() call alongside target_files.
    Caller-supplied params take precedence on key collision.

    Errors are caught and recorded on the row; this function never
    raises into the background task scheduler.
    """
    await _update_fix_run_status(session, run_id, "executing", started=True)

    try:
        executor = ActionExecutor(context)
        exec_kwargs: dict[str, Any] = {}
        if target_files is not None:
            exec_kwargs["target_files"] = target_files
        if params:
            exec_kwargs.update(params)
        action_result = await executor.execute(fix_id, write=write, **exec_kwargs)
    except Exception as exc:
        logger.exception("fix_runner: %s raised for %s", fix_id, run_id)
        await _update_fix_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    status = "completed" if action_result.ok else "failed"
    error_text = None if action_result.ok else str(action_result.data.get("error", ""))

    await _update_fix_run_status(
        session,
        run_id,
        status,
        finished=True,
        error=error_text,
        result={
            "ok": action_result.ok,
            "data": action_result.data,
            "duration_sec": action_result.duration_sec,
        },
    )

    logger.info(
        "fix_runner: %s (%s) completed status=%s ok=%s",
        run_id,
        fix_id,
        status,
        action_result.ok,
    )


# ID: 6c0712fe-1cb8-47ae-9de7-d51055b17cd0
async def run_and_persist_flow(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    flow_id: str,
    write: bool,
) -> None:
    """Execute a Flow and persist the result on the fix_runs row.

    Mirrors run_and_persist_fix but dispatches to FlowExecutor. The
    caller (the route handler) owns the row's `kind` column — this
    function only updates lifecycle state and the result payload.
    """
    await _update_fix_run_status(session, run_id, "executing", started=True)

    try:
        executor = FlowExecutor(context)
        flow_result = await executor.execute(flow_id, write=write)
    except Exception as exc:
        logger.exception("fix_runner: flow %s raised for %s", flow_id, run_id)
        await _update_fix_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    status = "completed" if flow_result.ok else "failed"
    error_text = None
    if not flow_result.ok:
        # Surface the first failed required step's error, if any.
        for step in flow_result.steps:
            if not step.ok and step.required:
                error_text = (
                    str(step.data.get("error", "")) or f"step {step.ref_id} failed"
                )
                break

    await _update_fix_run_status(
        session,
        run_id,
        status,
        finished=True,
        error=error_text,
        result={
            "ok": flow_result.ok,
            "flow_id": flow_result.flow_id,
            "duration_sec": flow_result.duration_sec,
            "steps": [
                {
                    "ref_id": step.ref_id,
                    "kind": step.kind,
                    "ok": step.ok,
                    "required": step.required,
                    "duration_sec": step.duration_sec,
                }
                for step in flow_result.steps
            ],
        },
    )

    logger.info(
        "fix_runner: flow %s (%s) completed status=%s ok=%s",
        run_id,
        flow_id,
        status,
        flow_result.ok,
    )


# ID: 23d15ca3-20a1-4f67-864e-cc44477936d1
async def run_and_persist_modularity(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    write: bool,
) -> None:
    """Execute the modularity remediation cycle and persist the result.

    Bridges to will.self_healing.ModularityRemediationService — there is
    no `flow.modularity` declaration, so this path runs directly against
    the closed-loop service that the CLI uses (see
    `cli/commands/fix/modularity.py`).

    The fix_runs row has already been INSERTed by the route handler with
    status='pending', kind='modularity', fix_id=NULL. This function
    transitions it through executing → completed / failed and writes a
    summary of the per-file remediation results into the result jsonb.
    """
    from will.self_healing.modularity_remediation_service import (
        ModularityRemediationService,
    )

    await _update_fix_run_status(session, run_id, "executing", started=True)

    try:
        service = ModularityRemediationService(context)
        results = await service.remediate_batch(write=write)
    except Exception as exc:
        logger.exception("fix_runner: modularity remediation raised for %s", run_id)
        await _update_fix_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    # remediate_batch returns a list of per-file dicts ({file, original_score,
    # success, message}). Empty list = no violators above threshold, which is
    # the success outcome — nothing to do.
    successes = sum(1 for r in results if r.get("success"))
    failures = len(results) - successes
    ok = failures == 0

    await _update_fix_run_status(
        session,
        run_id,
        "completed" if ok else "failed",
        finished=True,
        result={
            "ok": ok,
            "count": len(results),
            "successes": successes,
            "failures": failures,
            "files": results,
        },
    )

    logger.info(
        "fix_runner: modularity %s completed ok=%s files=%d successes=%d",
        run_id,
        ok,
        len(results),
        successes,
    )


# ID: 906b77f1-2ca4-461a-8227-e7b088d1cc1f
def bootstrap_ir(context: CoreContext, kind: str) -> str:
    """Write an IR scaffold file via FileHandler and return its path.

    `kind` selects the template ('triage' → .intent/mind/ir/triage_log.yaml,
    'log' → .intent/mind/ir/incident_log.yaml). Unknown kinds raise
    ValueError — the route handler translates that to 422.

    The write goes through context.file_handler.write_runtime_text so
    the operation remains under IntentGuard.
    """
    if kind not in _IR_FILES:
        raise ValueError(
            f"Unknown IR kind: {kind!r}. Allowed: {sorted(_IR_FILES.keys())}"
        )

    path, content = _IR_FILES[kind]
    rel_path = str(path).replace("\\", "/")
    context.file_handler.write_runtime_text(rel_path, content)
    return rel_path


# ----------------------------------------------------------------------
# /quality wiring (ADR-055 D3)
#
# Sync helpers return the inline ADR-055 D3 shape `{status, violations}`.
# The async dispatcher persists to fix_runs with kind='quality_check'
# and a per-check fix_id ('lint' | 'tests' | 'system' | 'gates').
# ----------------------------------------------------------------------


_QUALITY_GATES: list[tuple[str, list[str], bool]] = [
    # (display_name, argv, is_warning)
    # warning gates fail the row only when their exit code is non-zero
    # AND no critical gate failed — mirrors the CLI's --strict semantics
    # at PASS verdict level. Per ADR-055 D3 we record outcomes verbatim
    # and let callers interpret severity.
    ("ruff", ["ruff", "check", "src/"], False),
    ("mypy", ["mypy", "src/", "--ignore-missing-imports"], False),
    ("pytest", ["pytest", "-q", "--no-cov"], False),
    ("pip-audit", ["pip-audit"], False),
    ("radon", ["radon", "cc", "src/", "-nc", "-a"], True),
    ("vulture", ["vulture", "src/", "--min-confidence", "80"], True),
]


# ID: b64958a3-c4ec-4822-bf52-db5c25a1eb32
async def run_quality_imports(target_files: list[str] | None) -> dict:
    """Run the import-resolution check synchronously.

    Wraps body.atomic.check_actions.action_check_imports. `target_files`
    is accepted for forward compatibility with ADR-055 D3 but is not
    yet honored by the backend, which checks all of src/.
    """
    from body.atomic.check_actions import action_check_imports

    if target_files:
        logger.info(
            "run_quality_imports: target_files supplied but backend "
            "currently checks all of src/ — argument ignored"
        )

    result = await action_check_imports()
    return {
        "status": "ok" if result.ok else "failed",
        "violations": result.data.get("violations", []),
    }


# ID: 59c8771b-19bc-4933-ae34-9b8da796c9ca
async def run_quality_body_ui(
    context: CoreContext,
    target_files: list[str] | None,
) -> dict:
    """Run the Body-layer UI contract check synchronously.

    Wraps body.governance.body_contracts_service.check_body_contracts.
    `target_files` is accepted but not yet honored by the backend.
    """
    from body.governance.body_contracts_service import check_body_contracts

    if target_files:
        logger.info(
            "run_quality_body_ui: target_files supplied but backend "
            "currently scans the full body/ layer — argument ignored"
        )

    repo_root = context.git_service.repo_path
    result = await check_body_contracts(repo_root=repo_root)
    return {
        "status": "ok" if result.ok else "failed",
        "violations": result.data.get("violations", []),
    }


# ID: 4eb136d9-46ea-403f-9c0f-59a1eefddd8f
async def _run_subprocess(
    argv: list[str],
    cwd: Path | None,
) -> dict:
    """Run a subprocess via the sanctioned shared.utils.subprocess_utils
    primitive and shape the outcome for the result jsonb.

    Returns a JSON-safe summary the API can include in the fix_runs row.
    Never raises — subprocess failures are recorded as ok=False with
    the error in `summary`.
    """
    from shared.utils.subprocess_utils import run_command_async

    try:
        completed = await run_command_async(argv, cwd=cwd)
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "exit_code": -1,
            "summary": f"command not found: {argv[0]} ({exc})",
        }
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": -1,
            "summary": f"{type(exc).__name__}: {exc}",
        }

    stdout_tail = (completed.stdout or "").strip().splitlines()[-50:]
    stderr_tail = (completed.stderr or "").strip().splitlines()[-50:]

    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


# ID: 34305b01-d3c7-4452-b600-b51ec71aeea6
async def _run_quality_lint(context: CoreContext, fix: bool) -> dict:
    """Run ruff check on src/ (optionally with --fix). Subprocess-backed."""
    argv = ["ruff", "check", "src/"]
    if fix:
        argv.append("--fix")
    sub = await _run_subprocess(argv, cwd=context.git_service.repo_path)
    return {"check": "lint", "fix": fix, **sub}


# ID: ef67960d-a46e-4bca-9633-7fddc9d1bdba
async def _run_quality_tests(context: CoreContext, path: str | None) -> dict:
    """Run pytest, optionally scoped to a path."""
    argv = ["pytest", "-q", "--no-cov"]
    if path:
        argv.append(path)
    sub = await _run_subprocess(argv, cwd=context.git_service.repo_path)
    return {"check": "tests", "path": path, **sub}


# ID: 660686c7-ce64-4ceb-9351-810ba62eb74b
async def _run_quality_system(context: CoreContext) -> dict:
    """Run lint + tests in sequence — the /quality/system bundle.

    The audit step that the CLI version includes is reachable through
    POST /v1/audit/runs and is intentionally not duplicated here; callers
    that want both should issue two requests.
    """
    cwd = context.git_service.repo_path
    lint_sub = await _run_subprocess(["ruff", "check", "src/"], cwd=cwd)
    tests_sub = await _run_subprocess(["pytest", "-q", "--no-cov"], cwd=cwd)
    ok = lint_sub["ok"] and tests_sub["ok"]
    return {
        "check": "system",
        "ok": ok,
        "components": {
            "lint": lint_sub,
            "tests": tests_sub,
        },
    }


# ID: d767ebba-0520-42f7-ae75-cb42cf6c2a87
async def _run_quality_gates(context: CoreContext) -> dict:
    """Run the six industry-standard quality gates as subprocesses.

    Mirrors src/cli/commands/check/quality_gates.py without the Rich
    rendering. Critical-gate failure flips the row status to failed;
    warning gates record their result but do not change the verdict.
    """
    cwd = context.git_service.repo_path
    components: dict[str, dict] = {}
    any_critical_failed = False

    for name, argv, is_warning in _QUALITY_GATES:
        sub = await _run_subprocess(argv, cwd=cwd)
        components[name] = {**sub, "is_warning": is_warning}
        if not sub["ok"] and not is_warning:
            any_critical_failed = True

    return {
        "check": "gates",
        "ok": not any_critical_failed,
        "components": components,
    }


# ID: d001f68f-363e-43cf-9bac-3984d5d334dc
async def run_and_persist_quality(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    check: str,
    params: dict[str, Any],
) -> None:
    """Execute a quality check and persist the result on the fix_runs row.

    `check` ∈ {'lint', 'tests', 'system', 'gates'}. The row has already
    been INSERTed by the route handler with kind='quality_check',
    fix_id=check, status='pending'. This function transitions it
    through executing → completed / failed.

    Unknown check values resolve to 'failed' immediately — the route
    handler should never reach this branch because the FastAPI body
    schema constrains the discriminator at request time.
    """
    await _update_fix_run_status(session, run_id, "executing", started=True)

    try:
        if check == "lint":
            result_payload = await _run_quality_lint(
                context, fix=bool(params.get("fix", False))
            )
        elif check == "tests":
            result_payload = await _run_quality_tests(context, path=params.get("path"))
        elif check == "system":
            result_payload = await _run_quality_system(context)
        elif check == "gates":
            result_payload = await _run_quality_gates(context)
        else:
            await _update_fix_run_status(
                session,
                run_id,
                "failed",
                finished=True,
                error=f"unknown quality check: {check!r}",
            )
            return
    except Exception as exc:
        logger.exception("fix_runner: quality %s raised for %s", check, run_id)
        await _update_fix_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    ok = bool(result_payload.get("ok", False))
    await _update_fix_run_status(
        session,
        run_id,
        "completed" if ok else "failed",
        finished=True,
        error=None if ok else result_payload.get("summary"),
        result=result_payload,
    )

    logger.info(
        "fix_runner: quality %s (%s) completed ok=%s",
        run_id,
        check,
        ok,
    )
