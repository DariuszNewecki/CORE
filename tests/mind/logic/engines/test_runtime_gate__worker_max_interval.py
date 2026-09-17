"""Tests for runtime_gate.worker_max_interval_within_observed (#516, #856).

The check aggregates worker.heartbeat rows from core.blackboard_entries
per worker_uuid over a PER-WORKER window, max(24h, 11 x declared
max_interval) (governor ruling 2026-09-17, #895 cold review: a fixed 24h
window made the rule undecidable for 6h and daily workers), and fires when
the observed p95
inter-heartbeat gap exceeds the configured ``mandate.schedule.max_interval``
times 1.1. #856: workers with fewer than 10 samples, or a missing
db_session entirely, no longer skip silently -- both surface as one
aggregated ENFORCEMENT_UNAVAILABLE finding (governor rulings 7-9), which
the audit-verdict policy routes to DEGRADED for this blocking rule.

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

from mind.logic.engines import runtime_gate
from mind.logic.engines.runtime_gate import (
    _check_worker_max_interval_within_observed,
    heartbeat_retention_hours,
    max_interval_lookback_hours,
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
async def test_db_session_absent_surfaces_unavailable(tmp_path: Path) -> None:
    """#856: if db_session is not injected (e.g. IntentGuard pre-commit
    path), the check no longer defers silently -- it surfaces one
    aggregated ENFORCEMENT_UNAVAILABLE finding naming the affected active
    workers. Unlike worker_process_classification (advisory sibling,
    silent-skip on missing evidence remains a reasonable choice there),
    this rule is blocking: missing db_session is unavailable evidence, not
    a silent pass (governor ruling 8)."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", "11111111-2222-3333-4444-555555555555", 600)

    ctx = SimpleNamespace(repo_path=tmp_path, db_session=None)
    out = await _check_worker_max_interval_within_observed(ctx)
    assert len(out) == 1
    finding = out[0]
    assert finding.check_id == "runtime.worker_max_interval_within_observed"
    assert finding.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert finding.context["reason"] == "db_session_unavailable"
    assert finding.context["affected_worker_stems"] == ["alpha"]


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
async def test_worker_insufficient_samples_surfaces_unavailable(
    tmp_path: Path,
) -> None:
    """#856: workers with fewer than the 10-sample minimum no longer skip
    silently -- right after a daemon restart the rule now surfaces one
    aggregated ENFORCEMENT_UNAVAILABLE finding (governor ruling 7) instead
    of a silent, indistinguishable-from-clean pass.
    """
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", "11111111-2222-3333-4444-555555555555", 600)

    # samples=5 (< 10) — must surface as unavailable even though p95
    # vastly exceeds threshold; insufficient evidence, not a clean pass.
    ctx = _ctx_with_rows(tmp_path, [SimpleNamespace(samples=5, p95=5000.0)])
    out = await _check_worker_max_interval_within_observed(ctx)
    assert len(out) == 1
    finding = out[0]
    assert finding.check_id == "runtime.worker_max_interval_within_observed"
    assert finding.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert finding.context["reason"] == "insufficient_samples"
    assert finding.context["affected_worker_stems"] == ["alpha"]
    assert finding.context["sample_counts"] == {"alpha": 5}


async def test_multiple_insufficient_samples_workers_aggregate_into_one_finding(
    tmp_path: Path,
) -> None:
    """#856 governor ruling 9: multiple workers with insufficient evidence
    in the same audit run produce ONE aggregated finding, not one per
    worker -- preserves GitHub's annotation budget."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", "11111111-2222-3333-4444-555555555555", 600)
    _write_worker_yaml(workers, "beta", "22222222-3333-4444-5555-666666666666", 600)

    # Two workers, each below the 10-sample minimum.
    ctx = _ctx_with_rows(
        tmp_path,
        [
            SimpleNamespace(samples=3, p95=100.0),
            SimpleNamespace(samples=7, p95=200.0),
        ],
    )
    out = await _check_worker_max_interval_within_observed(ctx)
    assert len(out) == 1
    finding = out[0]
    assert finding.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert set(finding.context["affected_worker_stems"]) == {"alpha", "beta"}
    assert finding.context["sample_counts"] == {"alpha": 3, "beta": 7}


async def test_missing_aggregate_row_counts_as_insufficient_samples(
    tmp_path: Path,
) -> None:
    """A worker with no aggregate row at all (row is None) is zero samples
    — folded into the same insufficient-evidence bucket as an explicit
    low sample count, not silently skipped."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", "11111111-2222-3333-4444-555555555555", 600)

    ctx = _ctx_with_rows(tmp_path, [None])
    out = await _check_worker_max_interval_within_observed(ctx)
    assert len(out) == 1
    finding = out[0]
    assert finding.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert finding.context["sample_counts"] == {"alpha": 0}


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


# ------------------------------------------------------------------------
# Per-worker evidence window (governor ruling 2026-09-17, exposed by #895)
# ------------------------------------------------------------------------


def _ctx_capturing_hours(repo_root: Path, rows: list[Any]):
    """Like _ctx_with_rows, but records the :hours bound parameter of every
    execute() so the window is asserted, not inferred."""
    seen: list[float] = []

    async def _execute(_stmt, params=None, **_kwargs):
        seen.append(float((params or {})["hours"]))
        return SimpleNamespace(first=lambda: rows.pop(0) if rows else None)

    session = SimpleNamespace(execute=AsyncMock(side_effect=_execute))
    return SimpleNamespace(repo_path=repo_root, db_session=session), seen


@pytest.fixture(autouse=True)
def _heartbeats_retained_unbounded(monkeypatch: pytest.MonkeyPatch):
    """Default: no TTL applies to worker.heartbeat (CORE's real configuration:
    only loop_hold.sample:: is under the telemetry TTL). Tests override."""
    monkeypatch.setattr(runtime_gate, "heartbeat_retention_hours", lambda: None)


@pytest.mark.parametrize(
    ("max_interval", "expected_hours"),
    [
        (600, 24.0),  # fast (10 min): 11 x 600s = 1.8h < 24h floor
        (7200, 24.0),  # 2h: 22h < 24h floor -- still the floor
        (21600, 66.0),  # six-hour worker: 11 x 6h = 66h
        (86400, 264.0),  # daily worker: 11 days
    ],
)
def test_lookback_is_max_of_floor_and_eleven_intervals(
    max_interval: int, expected_hours: float
) -> None:
    assert max_interval_lookback_hours(max_interval) == expected_hours


def test_lookback_is_uncapped_for_very_slow_workers() -> None:
    """No cap (governor ruling): a cap shorter than the required window
    recreates the defect the ruling fixes."""
    weekly = 7 * 86400
    assert max_interval_lookback_hours(weekly) == 11 * 7 * 24.0


async def test_six_hour_and_daily_workers_are_queried_over_their_own_windows(
    tmp_path: Path,
) -> None:
    """The three workers the 2026-09-17 DB-backed audit could never decide
    under a fixed 24h window each get a window that can hold ten gaps."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(
        workers, "archiver", "11111111-2222-3333-4444-555555555555", 86400
    )
    _write_worker_yaml(workers, "fast", "22222222-2222-3333-4444-555555555555", 600)
    _write_worker_yaml(
        workers, "janitor", "33333333-2222-3333-4444-555555555555", 21600
    )
    rows = [
        SimpleNamespace(samples=10, p95=86000.0),  # archiver: within cap
        SimpleNamespace(samples=120, p95=590.0),  # fast: within cap
        SimpleNamespace(samples=11, p95=21500.0),  # janitor: within cap
    ]
    ctx, hours_seen = _ctx_capturing_hours(tmp_path, rows)
    out = await _check_worker_max_interval_within_observed(ctx)
    assert out == []
    # sorted(glob) order: archiver, fast, janitor
    assert hours_seen == [264.0, 24.0, 66.0]


@pytest.mark.parametrize("phase_fraction", [0.0, 0.25, 0.5, 0.99, 0.999])
def test_window_boundary_timing_cannot_lose_the_tenth_gap(
    phase_fraction: float,
) -> None:
    """A worker heartbeating exactly at its declared cadence has its latest
    ten gaps spanning 10 x max_interval. The audit runs at an arbitrary
    moment inside the interval after the last heartbeat (phase 0..1), so a
    10-interval window would drop the oldest of those eleven heartbeats for
    any phase > 0 and leave nine gaps. The eleventh interval in the window
    covers every phase in [0, 1). Phase 1.0 is the instant the next
    heartbeat is due and the SQL's strict ``created_at >`` excludes the
    boundary row -- the degenerate case, not timing jitter. Residual, on
    record: heartbeats that are ALL late by the tolerated 1.1x spend the
    eleventh interval on jitter alone; that shows up as insufficient
    samples (UNAVAILABLE), never as a false pass."""
    max_interval = 21600
    window_sec = int(max_interval_lookback_hours(max_interval) * 3600)
    now = 10_000_000
    last = now - int(phase_fraction * max_interval)
    heartbeats = [last - k * max_interval for k in range(11)]  # 11 beats, 10 gaps
    in_window = [hb for hb in heartbeats if hb > now - window_sec]
    assert len(in_window) - 1 >= 10, (
        f"phase {phase_fraction}: only {len(in_window) - 1} gaps inside the window"
    )
    # and a 10-interval window WOULD lose it for any positive phase
    ten_interval_window = 10 * max_interval
    in_short = [hb for hb in heartbeats if hb > now - ten_interval_window]
    if phase_fraction > 0:
        assert len(in_short) - 1 < 10


async def test_insufficient_history_in_a_long_window_is_still_unavailable(
    tmp_path: Path,
) -> None:
    """A daily worker with only three gaps inside its 264h window: still
    insufficient evidence -> UNAVAILABLE, and the message no longer claims
    a 24h window it did not use."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(
        workers, "archiver", "11111111-2222-3333-4444-555555555555", 86400
    )
    ctx, hours_seen = _ctx_capturing_hours(
        tmp_path, [SimpleNamespace(samples=3, p95=86000.0)]
    )
    out = await _check_worker_max_interval_within_observed(ctx)
    assert hours_seen == [264.0]
    (finding,) = out
    assert finding.context["reason"] == "insufficient_samples"
    assert finding.context["sample_counts"] == {"archiver": 3}
    assert "24h —" not in finding.message
    assert "11 x declared max_interval" in finding.message


async def test_retention_shorter_than_required_window_is_unsatisfiable_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If heartbeats were retained for 7 days, a daily worker's 11-day
    window could never be filled: that is an unsatisfiable configuration,
    reported as such -- distinct from insufficient samples, never a worker
    failure -- and the DB is not even queried for that worker."""
    monkeypatch.setattr(runtime_gate, "heartbeat_retention_hours", lambda: 7 * 24.0)
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(
        workers, "archiver", "11111111-2222-3333-4444-555555555555", 86400
    )
    _write_worker_yaml(
        workers, "janitor", "33333333-2222-3333-4444-555555555555", 21600
    )
    ctx, hours_seen = _ctx_capturing_hours(
        tmp_path, [SimpleNamespace(samples=12, p95=21000.0)]
    )
    out = await _check_worker_max_interval_within_observed(ctx)
    assert hours_seen == [66.0], "only the satisfiable worker was queried"
    (finding,) = out
    assert finding.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert finding.context["reason"] == "retention_shorter_than_required_window"
    assert finding.context["affected_worker_stems"] == ["archiver"]
    assert finding.context["required_window_hours"] == {"archiver": 264.0}
    assert finding.context["retention_hours"] == 168.0
    assert finding.file_path == ".intent/enforcement/config/operational_config.yaml"
    assert "not a worker failure" in finding.message


def test_heartbeat_retention_reads_the_governed_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()  # drop the autouse stub; exercise the real reader
    from shared.infrastructure.intent import operational_config as oc

    def _cfg(prefixes: tuple[str, ...], days: int = 7):
        return SimpleNamespace(
            blackboard=SimpleNamespace(
                telemetry_subject_prefixes=prefixes, telemetry_ttl_days=days
            )
        )

    monkeypatch.setattr(
        oc, "load_operational_config", lambda: _cfg(("loop_hold.sample::",))
    )
    assert heartbeat_retention_hours() is None, "heartbeats are not under the TTL"
    monkeypatch.setattr(oc, "load_operational_config", lambda: _cfg(("worker.",), 3))
    assert heartbeat_retention_hours() == 72.0
