# src/will/governance/coverage_runner.py

"""
Coverage runner facade — Will-layer entry point for the /coverage API
(ADR-057 D1).

The /coverage namespace has two characters:

* **Read-only queries** (`GET`) — compliance check, text/HTML report,
  constitutional targets, gaps, history, method comparison. These query
  existing data and return synchronously.

* **Stateful generation** (`POST`) — adaptive test generation for a
  single file or a prioritised batch. Async; backed by
  `will.self_healing.coverage_remediation_service.remediate_coverage_enhanced`.
  Cycle rows live on core.coverage_runs.

All async runners share `_update_coverage_run_status` for the
pending → executing → completed | failed lifecycle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

from body.quality.coverage_analyzer import CoverageAnalyzer
from mind.governance.filtered_audit import run_filtered_audit
from shared.context import CoreContext
from shared.logger import getLogger
from shared.utils.subprocess_utils import run_command_async
from will.self_healing.coverage_remediation_service import (
    remediate_coverage_enhanced,
)


__all__ = [
    "get_coverage_check",
    "get_coverage_gaps",
    "get_coverage_history",
    "get_coverage_methods",
    "get_coverage_report",
    "get_coverage_targets",
    "run_and_persist_coverage_batch",
    "run_and_persist_coverage_generation",
    "run_tests_interactive",
]


logger = getLogger(__name__)


_COVERAGE_RULE_IDS = (
    "coverage.test_coverage_required",
    "test_coverage.required",
)

# #809: the route layer already rejects write=false before dispatch, but
# this facade advertises `write` as part of its own contract — a future or
# direct caller that bypasses the route must not have the flag silently
# disregarded. remediate_coverage_enhanced() has no dry-run mode; it writes
# unconditionally.
_WRITE_FALSE_UNSUPPORTED = (
    "write=false is unsupported: remediate_coverage_enhanced() has no "
    "dry-run contract and writes test files unconditionally. Pass "
    "write=true, or route through the sandboxed successor pipeline "
    "(IterativeCoderAgent / build.test_for_symbol) for a real preview."
)


# ID: 7c1d3e9a-8b5f-4a02-bc18-9e3d5f627c01
async def get_coverage_check(context: CoreContext) -> dict:
    """Run the constitutional coverage compliance check.

    Wraps the filtered-audit entry point with coverage rule_ids. Returns
    findings (one per file below the constitutional target) and a
    PASS / FAIL verdict.
    """
    auditor_ctx = context.auditor_context
    if auditor_ctx is None:
        raise RuntimeError("auditor_context not initialized on CoreContext")
    await auditor_ctx.load_knowledge_graph()
    findings, executed_ids, stats = await run_filtered_audit(
        auditor_ctx,
        rule_ids=list(_COVERAGE_RULE_IDS),
        policy_ids=[],
        files=None,
    )
    findings_dicts = [f.as_dict() if hasattr(f, "as_dict") else f for f in findings]
    passed = len(findings_dicts) == 0
    return {
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "finding_count": len(findings_dicts),
        "findings": findings_dicts,
        "executed_rule_ids": sorted(executed_ids),
        "stats": stats,
    }


# ID: 5e2b8a47-9d1c-43f0-bf6a-7e0d4f813b09
async def get_coverage_report(
    context: CoreContext, *, show_missing: bool = False
) -> dict:
    """Run pytest with coverage and return the text report.

    Subprocess-backed via the sanctioned run_command_async primitive.
    Returns the JSON-safe `{ok, exit_code, stdout_tail, stderr_tail}`
    shape; full report lives in `stdout_tail`.
    """
    argv = [
        "pytest",
        "--cov=src",
        "--cov-report=term" + (":skip-covered" if not show_missing else ""),
        "-q",
        "--no-header",
    ]
    cwd = context.git_service.repo_path
    try:
        completed = await run_command_async(argv, cwd=cwd)
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": -1,
            "summary": f"{type(exc).__name__}: {exc}",
            "stdout_tail": [],
            "stderr_tail": [],
        }
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout_tail": (completed.stdout or "").splitlines()[-200:],
        "stderr_tail": (completed.stderr or "").splitlines()[-50:],
    }


# ID: 8c4f1e9b-2a6d-4b73-9e80-1f2c3d4e5a6b
async def get_coverage_html_report(context: CoreContext) -> dict:
    """Run pytest with coverage and generate the HTML report directory.

    Subprocess-backed via the sanctioned run_command_async primitive.
    Closes #358. Returns the JSON-safe `{ok, exit_code, html_path,
    stdout_tail, stderr_tail}` shape; `html_path` is the repo-relative
    directory where the HTML report was written (None on failure).
    """
    argv = [
        "pytest",
        "--cov=src",
        "--cov-report=html",
        "-q",
        "--no-header",
    ]
    cwd = context.git_service.repo_path
    try:
        completed = await run_command_async(argv, cwd=cwd)
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": -1,
            "summary": f"{type(exc).__name__}: {exc}",
            "html_path": None,
            "stdout_tail": [],
            "stderr_tail": [],
        }
    htmlcov_dir = cwd / "htmlcov"
    html_path = "htmlcov" if htmlcov_dir.exists() else None
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "html_path": html_path,
        "stdout_tail": (completed.stdout or "").splitlines()[-50:],
        "stderr_tail": (completed.stderr or "").splitlines()[-50:],
    }


# ID: 9f6a4c2e-31b8-4d57-a9c0-2f6e7d8c5b14
def get_coverage_targets(context: CoreContext) -> dict:
    """Return the constitutional coverage targets.

    Reads `.intent/enforcement/config/test_coverage.yaml` through the
    sanctioned `IntentRepository.load_document` gateway — direct
    `yaml.safe_load` on `.intent/` content is forbidden by
    `architecture.namespace.no_direct_protected_access` (renamed #490;
    formerly `architecture.intent.non_gateway_no_direct_resolution`).
    """
    from shared.infrastructure.intent.intent_repository import (
        get_intent_repository,
    )

    rel_path = Path(".intent") / "enforcement" / "config" / "test_coverage.yaml"
    try:
        repo = get_intent_repository()
        repo.initialize()
        data = repo.load_document(rel_path) or {}
    except Exception as exc:
        logger.warning("coverage_runner: could not load test_coverage.yaml: %s", exc)
        data = {}
    return {
        "path": str(rel_path),
        "targets": data,
    }


# ID: 4d9e2f7a-58c3-4ba1-9e6f-3c4a7b6d8e21
def get_coverage_gaps(
    context: CoreContext,
    *,
    threshold: float = 75.0,
    limit: int = 20,
) -> dict:
    """Return modules ranked by coverage gap below threshold.

    Wraps body.quality.CoverageAnalyzer.get_module_coverage. Files with
    coverage at or above `threshold` are excluded. Results sorted by
    deficit (largest first).
    """
    repo_root = context.git_service.repo_path
    analyzer = CoverageAnalyzer(repo_root)
    coverage = analyzer.get_module_coverage()

    gaps = [
        {
            "file": file_path,
            "coverage": pct,
            "deficit": round(threshold - pct, 2),
        }
        for file_path, pct in coverage.items()
        if pct < threshold
    ]
    gaps.sort(key=lambda g: g["deficit"], reverse=True)  # type: ignore[arg-type, return-value]
    if limit > 0:
        gaps = gaps[:limit]

    return {
        "threshold": threshold,
        "count": len(gaps),
        "gaps": gaps,
    }


# ID: 6b1c4e8f-9a02-4d35-bf2a-7e8d3c4b9a1f
def get_coverage_history(context: CoreContext, *, limit: int = 30) -> dict:
    """Return recent coverage measurements from the runtime reports dir.

    The CLI writes coverage history to a JSON file under the runtime
    reports directory. This helper reads it back through PathResolver
    so the runtime path stays governed (no hardcoded directory
    literals — see `architecture.path_access.no_hardcoded_runtime_dirs`).
    Missing file → empty list.
    """
    from shared.path_resolver import PathResolver

    repo_root = context.git_service.repo_path
    history_file = PathResolver(repo_root).reports_dir / "coverage_history.json"
    if not history_file.exists():
        return {"count": 0, "history": []}
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("coverage_runner: could not read coverage_history.json: %s", exc)
        return {"count": 0, "history": []}

    history = data if isinstance(data, list) else data.get("entries", [])
    if limit > 0:
        history = history[-limit:]
    return {"count": len(history), "history": history}


# ID: 2a7b8c9d-3e4f-5a6b-7c8d-9e0f1a2b3c4d
def get_coverage_methods(context: CoreContext) -> dict:
    """Return the legacy-vs-adaptive coverage method comparison.

    For Phase 3 this returns the static method-descriptor payload — the
    actual comparison data lives on coverage_runs once batch generation
    has executed for both methods. Pre-cutover the CLI rendered this
    inline; the route exposes the descriptor so consumers can present it
    consistently.
    """
    return {
        "methods": [
            {
                "id": "legacy",
                "name": "Legacy coverage generator",
                "description": (
                    "Pre-ADR-014 generator: file-at-a-time, no prioritisation."
                ),
            },
            {
                "id": "adaptive",
                "name": "Adaptive coverage generator",
                "description": (
                    "ADR-014-era generator: gap-ranked batch with risk awareness."
                ),
            },
        ]
    }


# ID: a4b7c5d8-1e2f-3a4b-5c6d-7e8f9a0b1c2d
async def _update_coverage_run_status(
    session: Any,
    run_id: UUID,
    status: str,
    *,
    started: bool = False,
    finished: bool = False,
    error: str | None = None,
    result: dict | None = None,
) -> None:
    """Update a coverage_runs row's lifecycle state. Each call commits."""
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
        text(f"UPDATE core.coverage_runs SET {', '.join(sets)} WHERE id = :rid"),
        params,
    )
    await session.commit()


# ID: c3d5e7f9-2a4b-3c5d-7e9f-1b3d5e7f9a1c
async def run_and_persist_coverage_generation(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    target_file: str,
    write: bool,
) -> None:
    """Execute single-file adaptive test generation.

    The row has already been INSERTed by the route handler with
    status='pending' and the supplied target_file/write values. This
    function transitions it through executing → completed | failed.

    Failures (including the AuditorContext-missing case) are recorded
    on the row; this function never raises into the background-task
    scheduler.
    """
    await _update_coverage_run_status(session, run_id, "executing", started=True)

    if not write:
        await _update_coverage_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=_WRITE_FALSE_UNSUPPORTED,
        )
        return

    repo_root = context.git_service.repo_path
    file_path = (repo_root / target_file).resolve()
    if not file_path.exists() or not file_path.is_file():
        await _update_coverage_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"target_file does not exist: {target_file}",
        )
        return

    if context.cognitive_service is None or context.auditor_context is None:
        await _update_coverage_run_status(
            session, run_id, "failed", finished=True, error="Brain services unavailable"
        )
        return

    try:
        result = await remediate_coverage_enhanced(
            cognitive_service=context.cognitive_service,
            auditor_context=context.auditor_context,
            file_handler=context.file_service,
            repo_root=repo_root,
            file_path=file_path,
        )
    except Exception as exc:
        logger.exception(
            "coverage_runner: single-file remediation raised for %s", run_id
        )
        await _update_coverage_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    ok = bool(result.get("success", False)) if isinstance(result, dict) else False
    await _update_coverage_run_status(
        session,
        run_id,
        "completed" if ok else "failed",
        finished=True,
        error=None
        if ok
        else (result.get("error") if isinstance(result, dict) else None),
        result=result if isinstance(result, dict) else {"raw": str(result)},
    )

    logger.info(
        "coverage_runner: single-file %s completed target=%s ok=%s",
        run_id,
        target_file,
        ok,
    )


# ID: e5f7a9b1-3c5d-4e6f-7a8b-9c0d1e2f3a4b
async def run_and_persist_coverage_batch(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    batch_priority: str,
    write: bool,
) -> None:
    """Execute prioritised batch adaptive test generation.

    The row has already been INSERTed by the route handler with kind
    'batch' (target_file NULL, batch_priority='high'|'all'). This
    function transitions it through executing → completed | failed.
    """
    await _update_coverage_run_status(session, run_id, "executing", started=True)

    if not write:
        await _update_coverage_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=_WRITE_FALSE_UNSUPPORTED,
        )
        return

    repo_root = context.git_service.repo_path

    target_coverage = 90 if batch_priority == "high" else 75

    if context.cognitive_service is None or context.auditor_context is None:
        await _update_coverage_run_status(
            session, run_id, "failed", finished=True, error="Brain services unavailable"
        )
        return

    try:
        result = await remediate_coverage_enhanced(
            cognitive_service=context.cognitive_service,
            auditor_context=context.auditor_context,
            file_handler=context.file_service,
            repo_root=repo_root,
            target_coverage=target_coverage,
        )
    except Exception as exc:
        logger.exception("coverage_runner: batch remediation raised for %s", run_id)
        await _update_coverage_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    ok = bool(result.get("success", False)) if isinstance(result, dict) else False
    await _update_coverage_run_status(
        session,
        run_id,
        "completed" if ok else "failed",
        finished=True,
        error=None
        if ok
        else (result.get("error") if isinstance(result, dict) else None),
        result=result if isinstance(result, dict) else {"raw": str(result)},
    )

    logger.info(
        "coverage_runner: batch %s completed priority=%s ok=%s",
        run_id,
        batch_priority,
        ok,
    )


# ID: 98ebab69-eb10-4de4-b49d-28a670495a79
async def get_latest_coverage_report(
    session: Any, *, format: str | None = None
) -> dict | None:
    """Return the most recently completed coverage-report run's result.

    Report-runs are identified in ``core.coverage_runs`` by
    ``target_file IS NULL AND batch_priority IS NULL`` — those NULLs are
    the discriminator separating report-runs from generate-runs (which
    always have one or the other set). Filters to status='completed'
    and orders by finished_at descending.

    If *format* is supplied (``'text'`` or ``'html'``), filters to
    runs whose persisted ``result.format`` matches; otherwise returns
    the most recent regardless of format.

    Returns the row's ``result`` payload, or None if no completed
    report-run exists yet (the caller surfaces a 404 with a hint to
    POST /v1/coverage/reports).
    """
    if format is not None:
        sql = """
            SELECT result
              FROM core.coverage_runs
             WHERE target_file IS NULL
               AND batch_priority IS NULL
               AND status = 'completed'
               AND result ->> 'format' = :format
             ORDER BY finished_at DESC
             LIMIT 1
        """
        params = {"format": format}
    else:
        sql = """
            SELECT result
              FROM core.coverage_runs
             WHERE target_file IS NULL
               AND batch_priority IS NULL
               AND status = 'completed'
             ORDER BY finished_at DESC
             LIMIT 1
        """
        params = {}

    result = await session.execute(text(sql), params)
    row = result.first()
    if row is None:
        return None
    return row[0]


# ID: 64130eb6-26a8-4fcf-9604-f4894aebd10f
async def run_and_persist_coverage_report(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    format: str,
    show_missing: bool,
) -> None:
    """Run the pytest coverage report off the request thread (#608 fix).

    The row has already been INSERTed by ``POST /v1/coverage/reports``
    with ``target_file=NULL`` and ``batch_priority=NULL`` — those NULLs
    are the discriminator that distinguishes a report-run from a
    generate-run when ``GET /v1/coverage/report`` queries for the
    latest result.

    Transitions the row pending → executing → completed | failed. The
    pytest invocation is the same one ``get_coverage_report`` /
    ``get_coverage_html_report`` already do; moving it here keeps the
    HTTP GET cheap (which is what it should be) while preserving the
    underlying pytest-driven behavior. Failures are recorded on the row;
    this function never raises into the background-task scheduler.
    """
    await _update_coverage_run_status(session, run_id, "executing", started=True)

    try:
        if format == "html":
            result = await get_coverage_html_report(context)
        else:
            result = await get_coverage_report(context, show_missing=show_missing)
    except Exception as exc:
        logger.exception("coverage_runner: report run raised for %s", run_id)
        await _update_coverage_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    ok = bool(result.get("ok", False))
    payload = {
        "format": format,
        "show_missing": show_missing,
        **result,
    }
    await _update_coverage_run_status(
        session,
        run_id,
        "completed" if ok else "failed",
        finished=True,
        error=None if ok else result.get("summary") or "pytest non-zero exit",
        result=payload,
    )

    logger.info(
        "coverage_runner: report %s completed format=%s ok=%s",
        run_id,
        format,
        ok,
    )


# ID: f6a8b0c2-4d6e-5f7a-8b9c-0d1e2f3a4b5c
async def run_tests_interactive(
    context: CoreContext, *, target_file: str | None = None
) -> dict:
    """Synchronous interactive test-generation entry point.

    Per ADR-057 D5 this returns inline (no resource row, no background
    task). For Phase 3 the inline response is the result dict from
    `remediate_coverage_enhanced` keyed on the supplied target_file.
    Callers wanting full step-by-step control will iterate by re-issuing
    requests; the API does not hold session state.
    """
    repo_root = context.git_service.repo_path
    file_path: Path | None = None
    if target_file:
        file_path = (repo_root / target_file).resolve()
        if not file_path.exists() or not file_path.is_file():
            return {
                "ok": False,
                "error": f"target_file does not exist: {target_file}",
            }

    if context.cognitive_service is None or context.auditor_context is None:
        return {"ok": False, "error": "Brain services unavailable"}

    try:
        result = await remediate_coverage_enhanced(
            cognitive_service=context.cognitive_service,
            auditor_context=context.auditor_context,
            file_handler=context.file_service,
            repo_root=repo_root,
            file_path=file_path,
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return result if isinstance(result, dict) else {"raw": str(result)}
