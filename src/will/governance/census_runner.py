# src/will/governance/census_runner.py

"""
Census runner facade — Will-layer entry point for the /census API
(ADR-058 D1).

The /census namespace has two characters:

* **Stateful census run** — `POST /census/runs` triggers a CIM-0
  structural census, an async operation backed by
  `body.services.cim.CensusService.run_census`. The cycle row lives on
  `core.census_runs`; the RepoCensus artifact (Pydantic) lands in
  `result` as a JSON-serialised dict.

* **Synchronous baseline + diff queries** — baseline CRUD and diff
  comparison are inexpensive reads/writes against the on-disk
  `BaselineRegistry`. No resource table; no background tasks.

All async runners share `_update_census_run_status` for the
pending → executing → completed | failed lifecycle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

from body.services.cim.baselines import BaselineManager
from body.services.cim.census_service import CensusService
from body.services.cim.diff import DiffEngine
from body.services.cim.history import CensusHistory
from shared.context import CoreContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.workers.base import _sanitize_payload


__all__ = [
    "create_baseline",
    "get_diff",
    "list_baselines",
    "run_and_persist_census",
]


logger = getLogger(__name__)


def _cim_dir(repo_root: Path) -> Path:
    """Canonical CIM artifact directory under reports."""
    return PathResolver(repo_root).reports_dir / "cim"


def _baseline_registry_path(repo_root: Path) -> Path:
    return _cim_dir(repo_root) / "baselines.json"


def _history_dir(repo_root: Path) -> Path:
    return _cim_dir(repo_root) / "history"


# ID: 7d4f1e9a-3c8b-4e5d-9a2f-6b7c8d9e0f12
async def _update_census_run_status(
    session: Any,
    run_id: UUID,
    status: str,
    *,
    started: bool = False,
    finished: bool = False,
    error: str | None = None,
    result: dict | None = None,
    baseline_name: str | None = None,
) -> None:
    """Update a census_runs row's lifecycle state. Each call commits."""
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
        # Sanitize via the blackboard precedent — CIM payloads have rich
        # text fields that may contain non-ASCII (issue #359 closed
        # this hazard for audit findings; same applies here).
        params["result"] = json.dumps(_sanitize_payload(result), default=str)
    if baseline_name is not None:
        sets.append("baseline_name = :baseline_name")
        params["baseline_name"] = baseline_name

    await session.execute(
        text(f"UPDATE core.census_runs SET {', '.join(sets)} WHERE id = :rid"),
        params,
    )
    await session.commit()


# ID: 8e5a2f0b-4d9c-4f6e-bb3a-7c8d9e0f1234
async def run_and_persist_census(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    snapshot: bool,
) -> None:
    """Execute a CIM-0 census and persist the result on the run row.

    The row has been INSERTed by the route handler with status='pending'
    and the supplied `snapshot` flag. This function transitions it
    through executing → completed | failed. When `snapshot=True` the
    RepoCensus is also persisted to the on-disk history dir so a
    subsequent `POST /census/baselines/{name}` can promote it.
    """
    await _update_census_run_status(session, run_id, "executing", started=True)

    repo_root = context.git_service.repo_path

    try:
        service = CensusService()
        census = service.run_census(repo_path=repo_root)
    except Exception as exc:
        logger.exception("census_runner: run_census raised for %s", run_id)
        await _update_census_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    snapshot_file: str | None = None
    if snapshot:
        try:
            history = CensusHistory(
                _history_dir(repo_root), FileHandler(str(repo_root)), repo_root
            )
            snapshot_path = history.save_snapshot(census)
            snapshot_file = str(snapshot_path.relative_to(repo_root))
        except Exception as exc:
            logger.warning(
                "census_runner: snapshot persistence failed for %s: %s", run_id, exc
            )

    result = census.model_dump(mode="json")
    if snapshot_file:
        result["snapshot_file"] = snapshot_file

    await _update_census_run_status(
        session,
        run_id,
        "completed",
        finished=True,
        result=result,
    )

    logger.info(
        "census_runner: %s completed snapshot=%s",
        run_id,
        snapshot_file is not None,
    )


# ID: 9f6b3a1c-5e0d-4a7f-bc4b-8d9e0f1a2b34
def create_baseline(
    context: CoreContext,
    *,
    name: str,
    snapshot_file: str | None = None,
) -> dict:
    """Create a named baseline from a prior census snapshot.

    When `snapshot_file` is None, the most recent snapshot is used. The
    baseline registry is on-disk JSON managed by `BaselineManager`.
    Returns the baseline record as a dict; raises ValueError when no
    snapshot is available.
    """
    repo_root = context.git_service.repo_path
    file_handler = FileHandler(str(repo_root))
    manager = BaselineManager(
        _baseline_registry_path(repo_root), file_handler, repo_root
    )

    if snapshot_file is None:
        history = CensusHistory(_history_dir(repo_root), file_handler, repo_root)
        latest = history.get_latest_snapshot()
        if latest is None:
            raise ValueError(
                "No census snapshot available; run POST /census/runs with "
                "snapshot=true first."
            )
        snapshot_file = (
            history.list_snapshots()[0].name if history.list_snapshots() else None
        )
        if snapshot_file is None:
            raise ValueError("Snapshot history is empty.")

    try:
        sha = context.git_service.get_current_commit()[:40]
    except Exception:
        sha = None

    baseline = manager.set_baseline(
        name=name, snapshot_file=snapshot_file, git_commit=sha
    )
    return baseline.model_dump(mode="json")


# ID: 0a7c4b2d-6f1e-4b8a-c5d6-9e0f1a2b3c45
def list_baselines(context: CoreContext) -> dict:
    """List all named baselines (newest first)."""
    repo_root = context.git_service.repo_path
    file_handler = FileHandler(str(repo_root))
    manager = BaselineManager(
        _baseline_registry_path(repo_root), file_handler, repo_root
    )
    baselines = manager.list_baselines()
    return {
        "count": len(baselines),
        "baselines": [b.model_dump(mode="json") for b in baselines],
    }


# ID: 1b8d5c3e-7a2f-4c9b-d6e7-0f1a2b3c4d56
def get_diff(
    context: CoreContext,
    *,
    baseline: str | None = None,
) -> dict:
    """Diff the current snapshot against a baseline (or the previous one).

    When `baseline` is None, compares the latest snapshot against the
    immediately preceding one. When supplied, the baseline name is
    resolved through `BaselineManager` and the referenced snapshot is
    loaded from `CensusHistory`.
    """
    repo_root = context.git_service.repo_path
    file_handler = FileHandler(str(repo_root))
    history = CensusHistory(_history_dir(repo_root), file_handler, repo_root)
    latest = history.get_latest_snapshot()
    if latest is None:
        return {"available": False, "error": "No census snapshot available."}

    if baseline is None:
        previous = history.get_previous_snapshot()
        if previous is None:
            return {
                "available": False,
                "error": "Only one census snapshot exists; nothing to diff.",
            }
    else:
        manager = BaselineManager(
            _baseline_registry_path(repo_root), file_handler, repo_root
        )
        record = manager.get_baseline(baseline)
        if record is None:
            return {
                "available": False,
                "error": f"Baseline not found: {baseline}",
            }
        previous = history.load_snapshot(record.snapshot_file)

    engine = DiffEngine()
    diff = engine.compute_diff(previous=previous, current=latest)
    return {
        "available": True,
        "baseline": baseline,
        "diff": diff.model_dump(mode="json"),
    }
