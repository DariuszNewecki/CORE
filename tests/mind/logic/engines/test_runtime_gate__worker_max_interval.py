"""Tests for runtime_gate.worker_max_interval_within_observed (#516).

The check aggregates worker.heartbeat rows from core.blackboard_entries
per worker_uuid over a 24h window and fires when the observed p95
inter-heartbeat gap exceeds the configured ``mandate.schedule.max_interval``
times 1.1. Workers with fewer than 10 samples are skipped silently.

These tests stub the DB session with a lightweight async-shaped fake so
the check's algorithm is exercised without a real Postgres dependency.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import yaml

from mind.logic.engines.runtime_gate import (
    _check_worker_max_interval_within_observed,
)


def _write_worker_yaml(
    workers_dir: Path,
    stem: str,
    uuid_str: str,
    max_interval: int | None,
    status: str = "active",
) -> None:
    """Drop a minimal worker.yaml matching the project's actual shape."""
    decl: dict[str, Any] = {
        "$schema": "META/worker.schema.json",
        "kind": "worker",
        "metadata": {
            "id": f"workers.{stem}",
            "title": stem,
            "version": "1.0.0",
            "authority": "policy",
            "status": status,
        },
        "identity": {"uuid": uuid_str, "class": "acting"},
        "mandate": {"responsibility": "test", "phase": "execution"},
        "implementation": {
            "module": f"will.workers.{stem}",
            "class": "X",
        },
    }
    if max_interval is not None:
        decl["mandate"]["schedule"] = {"max_interval": max_interval}
    (workers_dir / f"{stem}.yaml").write_text(yaml.dump(decl), encoding="utf-8")


def _ctx_with_rows(repo_root: Path, rows: list[Any]):
    """Build an AuditorContext shim whose db_session returns `rows` for any
    .execute() call. The check loops over each worker; a single canned
    result is reused per iteration via side_effect=list.
    """

    async def _execute(*_args, **_kwargs):
        result_mock = SimpleNamespace(first=lambda: rows.pop(0) if rows else None)
        return result_mock

    session = SimpleNamespace(execute=AsyncMock(side_effect=_execute))
    return SimpleNamespace(repo_path=repo_root, db_session=session)


# ID: 7ff0e1c4-3e46-4f7e-93e6-9f4fb0af3551
async def test_no_workers_no_findings(tmp_path: Path) -> None:
    """No worker YAMLs -> no findings; the check returns early."""
    (tmp_path / ".intent" / "workers").mkdir(parents=True)
    ctx = _ctx_with_rows(tmp_path, [])
    out = await _check_worker_max_interval_within_observed(ctx)
    assert out == []


# ID: 2b8c96f0-cb5a-4e7f-b437-dee4f9ca77cf
async def test_db_session_absent_returns_empty(tmp_path: Path) -> None:
    """If db_session is not injected (e.g. IntentGuard pre-commit path),
    the check defers without firing. Matches the precedent set by
    worker_process_classification."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", "11111111-2222-3333-4444-555555555555", 600)

    ctx = SimpleNamespace(repo_path=tmp_path, db_session=None)
    out = await _check_worker_max_interval_within_observed(ctx)
    assert out == []


# ID: 8e2db2e0-d3ce-4dcc-8fb5-132236c0c92e
async def test_worker_within_threshold_no_finding(tmp_path: Path) -> None:
    """Worker whose observed p95 is below configured x 1.1 produces no
    finding. cfg=600, observed p95=620 -> threshold=660, below."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", "11111111-2222-3333-4444-555555555555", 600)

    # Single row matches the SQL aggregate shape: (samples, p95).
    ctx = _ctx_with_rows(tmp_path, [SimpleNamespace(samples=50, p95=620.0)])
    out = await _check_worker_max_interval_within_observed(ctx)
    assert out == []


# ID: bb4fac7f-93c5-4a03-8202-3ba14b1dfe8c
async def test_worker_above_threshold_fires_finding(tmp_path: Path) -> None:
    """Worker whose observed p95 exceeds configured x 1.1 produces one
    finding with structured context.
    """
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", "11111111-2222-3333-4444-555555555555", 600)

    # p95=900, configured=600 -> threshold=660; 900>660 fires.
    ctx = _ctx_with_rows(tmp_path, [SimpleNamespace(samples=50, p95=900.0)])
    out = await _check_worker_max_interval_within_observed(ctx)
    assert len(out) == 1
    f = out[0]
    assert f.check_id == "runtime.worker_max_interval_within_observed"
    assert f.context["stem"] == "alpha"
    assert f.context["configured_max_interval_sec"] == 600
    assert f.context["observed_p95_gap_sec"] == 900.0
    assert f.context["samples"] == 50
    # suggested rounds up to next 60s above p95=900 -> 960
    assert f.context["suggested_max_interval_sec"] == 960
    assert f.file_path == ".intent/workers/alpha.yaml"


# ID: 3a8bc311-d9e7-4d72-857c-3c5b43d7c4a5
async def test_worker_insufficient_samples_skips_silently(tmp_path: Path) -> None:
    """Workers with fewer than the 10-sample minimum are skipped silently
    (no finding either way). Right after a daemon restart the rule
    reports clean until evidence accumulates.
    """
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", "11111111-2222-3333-4444-555555555555", 600)

    # samples=5 (< 10) — should skip even though p95 vastly exceeds
    # threshold.
    ctx = _ctx_with_rows(tmp_path, [SimpleNamespace(samples=5, p95=5000.0)])
    out = await _check_worker_max_interval_within_observed(ctx)
    assert out == []


async def test_paused_worker_skipped(tmp_path: Path) -> None:
    """Workers with metadata.status != 'active' are not evaluated."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(
        workers,
        "alpha",
        "11111111-2222-3333-4444-555555555555",
        600,
        status="paused",
    )

    ctx = _ctx_with_rows(tmp_path, [SimpleNamespace(samples=50, p95=9000.0)])
    out = await _check_worker_max_interval_within_observed(ctx)
    assert out == []


async def test_worker_without_max_interval_skipped(tmp_path: Path) -> None:
    """Workers whose YAML declares no mandate.schedule.max_interval are
    skipped — the rule only evaluates declarations against their own
    contract, not absent ones.
    """
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(
        workers,
        "alpha",
        "11111111-2222-3333-4444-555555555555",
        max_interval=None,
    )

    ctx = _ctx_with_rows(tmp_path, [SimpleNamespace(samples=50, p95=9000.0)])
    out = await _check_worker_max_interval_within_observed(ctx)
    assert out == []


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
