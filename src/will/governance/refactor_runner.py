# src/will/governance/refactor_runner.py

"""
Refactor runner facade — Will-layer entry point for the /refactor API
(ADR-057 D2).

The /refactor namespace has two characters:

* **Read-only queries** — per-file modularity score, files exceeding the
  threshold, aggregate distribution, threshold from constitution. These
  query the modularity engine and return synchronously. Backed by
  `mind.logic.engines.ast_gate.checks.modularity_checks.ModularityChecker`
  and `mind.governance.enforcement_loader.EnforcementMappingLoader`.

* **Stateful autonomous cycle** — POST /refactor/autonomous triggers the
  A3 loop (`will.autonomy.autonomous_developer.develop_from_goal`). The
  cycle row lives on core.refactor_runs; the proposals it generates land
  on core.autonomous_proposals. The result jsonb carries the proposal
  ids captured during the run window.

All async runners share `_update_refactor_run_status` for the
pending → executing → completed | failed lifecycle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.context import CoreContext
from shared.logger import getLogger
from will.autonomy.autonomous_developer import develop_from_goal


__all__ = [
    "get_refactor_candidates",
    "get_refactor_score",
    "get_refactor_stats",
    "get_refactor_threshold",
    "run_and_persist_refactor_autonomous",
]


logger = getLogger(__name__)


_SKIP_DIRS = {
    ".venv",
    "venv",
    ".git",
    "work",
    "var",
    "__pycache__",
    ".pytest_cache",
    "tests",
    "migrations",
    "reports",
}


# ID: 8a91b3c5-21f4-4dbf-bda9-7e3f4c81a5d9
def _enumerate_src_files(repo_root: Path) -> list[Path]:
    """Return Python source files under repo_root/src, skipping junk dirs."""
    src_root = repo_root / "src"
    if not src_root.exists():
        return []
    return [
        f
        for f in src_root.rglob("*.py")
        if not any(part in _SKIP_DIRS for part in f.parts)
    ]


# ID: f3b2c947-5e1d-4a6f-bdb8-0c8af6e74f31
def _analyze_one(checker: ModularityChecker, file_path: Path) -> dict | None:
    """Return per-file modularity details, or None when no findings."""
    findings = checker.check_refactor_score(file_path, {"max_score": 0})
    if not findings:
        return None
    return findings[0]["details"]


# ID: 6c2d5e8b-7f10-4b3a-a4b9-9d2f7c3e6b18
def get_refactor_threshold(repo_root: Path) -> float:
    """Return the authoritative modularity threshold from the constitution.

    Mirrors `refactor_support.config.get_modularity_threshold` so the
    behaviour the CLI observed pre-cutover is preserved through the API.
    """
    try:
        loader = EnforcementMappingLoader(repo_root / ".intent")
        strategy = loader.get_enforcement_strategy(
            "modularity.refactor_score_threshold"
        )
        if strategy and "params" in strategy:
            return float(strategy["params"].get("max_score", 60.0))
    except Exception as exc:
        logger.debug("refactor_runner: could not load modularity threshold: %s", exc)
    return 60.0


# ID: 2e7f8a4b-1c3d-4e5f-9a8b-7c6d5e4f3a2b
def get_refactor_score(repo_root: Path, relative_file_path: str) -> dict:
    """Per-file modularity score.

    Returns a dict with `file`, `score`, `details`, and a `found` flag.
    Missing files resolve to `{found: False, score: 0, details: None}` —
    the route handler maps that to 404.
    """
    abs_path = (repo_root / relative_file_path).resolve()
    if not abs_path.exists() or not abs_path.is_file():
        return {
            "file": relative_file_path,
            "found": False,
            "score": 0.0,
            "details": None,
        }

    checker = ModularityChecker()
    details = _analyze_one(checker, abs_path)
    if details is None:
        return {
            "file": relative_file_path,
            "found": True,
            "score": 0.0,
            "details": None,
        }
    return {
        "file": relative_file_path,
        "found": True,
        "score": float(details.get("total_score", 0.0)),
        "details": details,
    }


# ID: 9b4f3e2a-6c7d-4e8f-a1b2-3c4d5e6f7a89
def get_refactor_candidates(
    repo_root: Path,
    min_score: float | None = None,
    limit: int | None = None,
) -> dict:
    """Return files whose modularity score is at or above the threshold.

    When `min_score` is None the constitutional threshold is used. Results
    are sorted highest score first. `limit` truncates the list when set.
    """
    threshold = (
        get_refactor_threshold(repo_root) if min_score is None else float(min_score)
    )
    checker = ModularityChecker()
    files = _enumerate_src_files(repo_root)

    candidates: list[dict[str, Any]] = []
    for file in files:
        try:
            details = _analyze_one(checker, file)
        except Exception:
            continue
        if details is None:
            continue
        score = float(details.get("total_score", 0.0))
        if score < threshold:
            continue
        candidates.append(
            {
                "file": str(file.relative_to(repo_root)),
                "score": score,
                "responsibility_count": int(details.get("responsibility_count", 0)),
                "lines_of_code": int(details.get("lines_of_code", 0)),
            }
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    if limit is not None and limit > 0:
        candidates = candidates[:limit]

    return {
        "threshold": threshold,
        "count": len(candidates),
        "candidates": candidates,
    }


# ID: 4a8b9c0d-2e1f-4d3a-b5c6-7e8f9a0b1c2d
def get_refactor_stats(repo_root: Path) -> dict:
    """Aggregate modularity-score distribution across the codebase.

    Returns counts, mean, max, min, and a five-bucket histogram. Files
    that produce no score (the analyzer's "exceptionally clean" branch)
    are not counted.
    """
    checker = ModularityChecker()
    files = _enumerate_src_files(repo_root)
    scores: list[float] = []
    for file in files:
        try:
            details = _analyze_one(checker, file)
        except Exception:
            continue
        if details is None:
            continue
        scores.append(float(details.get("total_score", 0.0)))

    if not scores:
        return {
            "count": 0,
            "mean": 0.0,
            "max": 0.0,
            "min": 0.0,
            "histogram": {},
        }

    buckets = {
        "0-20": 0,
        "20-40": 0,
        "40-60": 0,
        "60-80": 0,
        "80+": 0,
    }
    for s in scores:
        if s < 20:
            buckets["0-20"] += 1
        elif s < 40:
            buckets["20-40"] += 1
        elif s < 60:
            buckets["40-60"] += 1
        elif s < 80:
            buckets["60-80"] += 1
        else:
            buckets["80+"] += 1

    return {
        "count": len(scores),
        "mean": sum(scores) / len(scores),
        "max": max(scores),
        "min": min(scores),
        "histogram": buckets,
    }


# ID: 5b7c8d9e-3f4a-4d2b-9c1a-8e7f6d5c4b3a
async def _update_refactor_run_status(
    session: Any,
    run_id: UUID,
    status: str,
    *,
    started: bool = False,
    finished: bool = False,
    error: str | None = None,
    result: dict | None = None,
) -> None:
    """Update a refactor_runs row's lifecycle state. Each call commits."""
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
        text(f"UPDATE core.refactor_runs SET {', '.join(sets)} WHERE id = :rid"),
        params,
    )
    await session.commit()


# ID: 3c1d2e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f
async def run_and_persist_refactor_autonomous(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    goal: str,
    write: bool,
) -> None:
    """Execute the A3 autonomous refactor cycle and persist on refactor_runs.

    The row has already been INSERTed by the route handler with status
    'pending' and the supplied `goal` + `write` values. This function
    transitions it through executing → completed | failed, and writes
    the captured proposal_ids into the result jsonb.

    Proposal capture: the autonomous_developer writes to
    `core.autonomous_proposals` as it runs. We snapshot the timestamp
    on entry and read back any proposal rows created during the cycle
    window. This is the same correlation the CLI used pre-cutover.

    Errors are caught and recorded on the row; this function never
    raises into the background-task scheduler.
    """
    await _update_refactor_run_status(session, run_id, "executing", started=True)

    started_at_result = await session.execute(
        text("SELECT started_at FROM core.refactor_runs WHERE id = :rid"),
        {"rid": run_id},
    )
    started_at_row = started_at_result.first()
    started_at = started_at_row[0] if started_at_row else None

    try:
        success, message = await develop_from_goal(
            context,
            goal=goal,
            workflow_type="refactor_modularity",
            write=write,
        )
    except Exception as exc:
        logger.exception("refactor_runner: develop_from_goal raised for %s", run_id)
        await _update_refactor_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    proposal_ids: list[str] = []
    if started_at is not None:
        try:
            proposals_result = await session.execute(
                text(
                    """
                    SELECT proposal_id
                      FROM core.autonomous_proposals
                     WHERE created_at >= :started_at
                     ORDER BY created_at ASC
                    """
                ),
                {"started_at": started_at},
            )
            proposal_ids = [str(row[0]) for row in proposals_result.all()]
        except Exception as exc:
            logger.warning(
                "refactor_runner: proposal correlation failed for %s: %s",
                run_id,
                exc,
            )

    await _update_refactor_run_status(
        session,
        run_id,
        "completed" if success else "failed",
        finished=True,
        error=None if success else message,
        result={
            "success": success,
            "message": message,
            "proposal_ids": proposal_ids,
            "proposal_count": len(proposal_ids),
        },
    )

    logger.info(
        "refactor_runner: %s completed success=%s proposals=%d",
        run_id,
        success,
        len(proposal_ids),
    )
