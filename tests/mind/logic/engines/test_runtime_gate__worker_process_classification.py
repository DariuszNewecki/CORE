# tests/mind/logic/engines/test_runtime_gate__worker_process_classification.py
"""Tests for runtime_gate.worker_process_classification (ADR-081 D7 / ADR-082).

ADR-082 replaced rolling-N (cycle_window) with time-bucketed windows:
- Escalation: max loop-hold in the last 24h (not the most-recent 5 samples).
- De-escalation: 168h window + heartbeat activity proof.

The tests stub the DB session to exercise the algorithm without a real
Postgres dependency. Key coverage:

1. Episodic perpetrator caught: recent samples below gate, 24h max above.
2. Escalation fires when 24h max > escalation_sec.
3. Escalation: insufficient samples (<3) → skip silently.
4. De-escalation fires when heartbeats ≥ min and 168h max < deescalation_sec.
5. De-escalation: insufficient heartbeats → skip silently.
6. De-escalation: no loop-hold samples in window → max=0 → fires (silence
   from event-driven instrument is affirmative evidence of cleanliness).
7. De-escalation: dedicated but still loud (max > 1s) → no finding.
8. No db_session → returns [].
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import yaml

from mind.logic.engines.runtime_gate import (
    _check_worker_process_classification,
)


pytestmark = [pytest.mark.integration]

_WORKER_UUID = "11111111-2222-3333-4444-555555555555"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_worker_yaml(
    workers_dir: Path,
    stem: str,
    *,
    uuid_str: str = _WORKER_UUID,
    requires_dedicated: bool = False,
    status: str = "active",
) -> None:
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
        "mandate": {
            "responsibility": "test",
            "phase": "execution",
            "schedule": {"max_interval": 300},
        },
        "implementation": {
            "module": f"will.workers.{stem}",
            "class": "X",
            "requires_dedicated_process": requires_dedicated,
        },
    }
    (workers_dir / f"{stem}.yaml").write_text(yaml.dump(decl), encoding="utf-8")


class _FakeResult:
    """Supports both `for row in r` (samples query) and `r.first()` (hb query)."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


def _sample_rows(durations: list[float]) -> list[Any]:
    return [SimpleNamespace(duration_sec=str(d)) for d in durations]


def _hb_row(count: int) -> Any:
    return SimpleNamespace(hb_count=count)


def _ctx(repo_root: Path, execute_responses: list[Any]) -> Any:
    """Build an AuditorContext shim whose db_session returns successive
    _FakeResult objects for each execute() call."""
    idx = [0]

    async def _execute(*_args, **_kwargs) -> _FakeResult:
        resp = execute_responses[idx[0]]
        idx[0] += 1
        if isinstance(resp, _FakeResult):
            return resp
        if isinstance(resp, list):
            return _FakeResult(resp)
        # Single row (e.g. heartbeat count) — wrap in list
        return _FakeResult([resp])

    session = SimpleNamespace(execute=AsyncMock(side_effect=_execute))
    return SimpleNamespace(repo_path=repo_root, db_session=session)


# ---------------------------------------------------------------------------
# Escalation tests (shares_process workers)
# ---------------------------------------------------------------------------


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
async def test_no_db_session_returns_empty(tmp_path: Path) -> None:
    """If db_session is not injected the check defers without firing."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha")

    ctx = SimpleNamespace(repo_path=tmp_path, db_session=None)
    out = await _check_worker_process_classification(ctx)
    assert out == []


# ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
async def test_no_workers_no_findings(tmp_path: Path) -> None:
    """No worker YAMLs → no findings."""
    (tmp_path / ".intent" / "workers").mkdir(parents=True)
    ctx = _ctx(tmp_path, [])
    out = await _check_worker_process_classification(ctx)
    assert out == []


# ID: c3d4e5f6-a7b8-9012-cdef-123456789012
async def test_escalation_fires_on_24h_max(tmp_path: Path) -> None:
    """shares_process worker with 24h max > 5s fires escalation_required."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=False)

    # 10 samples; max = 8.5s > 5.0s gate
    durations = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 8.5]
    ctx = _ctx(tmp_path, [_sample_rows(durations)])
    out = await _check_worker_process_classification(ctx)

    assert len(out) == 1
    f = out[0]
    assert f.check_id == "runtime.worker_process_classification"
    assert f.context["verdict"] == "escalation_required"
    assert f.context["stem"] == "alpha"
    assert f.context["max_loop_hold_sec"] == pytest.approx(8.5)
    assert f.context["sample_count"] == 10
    assert f.context["escalation_hours"] == 24
    assert ".intent/workers/alpha.yaml" in f.file_path
    assert "escalation_required" in f.message
    assert "24h" in f.message


# ID: d4e5f6a7-b8c9-0123-def0-234567890123
async def test_escalation_episodic_perpetrator(tmp_path: Path) -> None:
    """Core #597 case: recent-5 max below gate, 24h max above gate.

    Under the old rolling-N logic, only the 5 most-recent samples were
    considered; an episodic perpetrator whose bad spike had aged past
    position 5 was silently missed. The time-bucketed window catches it.
    """
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=False)

    # 10 samples returned by the time-bucketed query.
    # The 5 most-recent are all below 5s; the 24h max (position [9]) = 11.18s.
    durations = [4.37, 3.5, 2.1, 1.8, 1.2, 5.5, 6.0, 8.0, 9.5, 11.18]
    ctx = _ctx(tmp_path, [_sample_rows(durations)])
    out = await _check_worker_process_classification(ctx)

    assert len(out) == 1
    assert out[0].context["verdict"] == "escalation_required"
    assert out[0].context["max_loop_hold_sec"] == pytest.approx(11.18)


# ID: e5f6a7b8-c9d0-1234-ef01-345678901234
async def test_escalation_no_finding_when_below_gate(tmp_path: Path) -> None:
    """shares_process worker with 24h max < 5s produces no finding."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=False)

    durations = [0.1, 0.2, 0.3, 0.4, 0.5]
    ctx = _ctx(tmp_path, [_sample_rows(durations)])
    out = await _check_worker_process_classification(ctx)
    assert out == []


# ID: f6a7b8c9-d0e1-2345-f012-456789012345
async def test_escalation_insufficient_samples_skips_silently(tmp_path: Path) -> None:
    """Fewer than min_samples_for_escalation (default 3) → skip silently.

    This replaces the old cycle_window=5 floor. Two samples is suspicious
    (implies very recent restart or very rare emitter); no verdict issued.
    """
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=False)

    # Only 2 samples — below the 3-sample floor
    ctx = _ctx(tmp_path, [_sample_rows([99.9, 88.8])])
    out = await _check_worker_process_classification(ctx)
    assert out == []


# ID: a7b8c9d0-e1f2-3456-0123-567890123456
async def test_escalation_exactly_at_gate_no_finding(tmp_path: Path) -> None:
    """max == escalation_sec is not > gate — no finding (strict greater-than)."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=False)

    ctx = _ctx(tmp_path, [_sample_rows([5.0, 5.0, 5.0])])
    out = await _check_worker_process_classification(ctx)
    assert out == []


# ---------------------------------------------------------------------------
# De-escalation tests (requires_dedicated_process workers)
# ---------------------------------------------------------------------------


# ID: b8c9d0e1-f2a3-4567-1234-678901234567
async def test_deescalation_fires_with_heartbeat_proof(tmp_path: Path) -> None:
    """Dedicated worker, 15 heartbeats, 168h max < 1s → deescalation_candidate."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=True)

    # Two execute() calls: heartbeat count, then loop-hold samples
    ctx = _ctx(
        tmp_path,
        [
            _FakeResult([_hb_row(15)]),           # heartbeat count query
            _sample_rows([0.4, 0.5, 0.3, 0.6]),   # loop-hold samples
        ],
    )
    out = await _check_worker_process_classification(ctx)

    assert len(out) == 1
    f = out[0]
    assert f.context["verdict"] == "deescalation_candidate"
    assert f.context["stem"] == "alpha"
    assert f.context["max_loop_hold_sec"] == pytest.approx(0.6)
    assert f.context["active_heartbeats"] == 15
    assert f.context["deescalation_hours"] == 168
    assert "deescalation_candidate" in f.message
    assert "168h" in f.message


# ID: c9d0e1f2-a3b4-5678-2345-789012345678
async def test_deescalation_no_samples_fires(tmp_path: Path) -> None:
    """Dedicated worker with heartbeats but zero loop-hold samples in 168h.

    Silence from an event-driven instrument means the threshold was never
    tripped. max is treated as 0 < 1s gate → fires deescalation_candidate.
    This is ADR-082 D2's affirmative-silence clause.
    """
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=True)

    ctx = _ctx(
        tmp_path,
        [
            _FakeResult([_hb_row(20)]),  # 20 heartbeats
            _sample_rows([]),            # no loop-hold samples at all
        ],
    )
    out = await _check_worker_process_classification(ctx)

    assert len(out) == 1
    assert out[0].context["verdict"] == "deescalation_candidate"
    assert out[0].context["max_loop_hold_sec"] == pytest.approx(0.0)
    assert out[0].context["sample_count"] == 0


# ID: d0e1f2a3-b4c5-6789-3456-890123456789
async def test_deescalation_insufficient_heartbeats_skips(tmp_path: Path) -> None:
    """Dedicated worker but only 5 heartbeats in 168h → skip silently.

    Cannot distinguish 'truly clean' from 'not running'; defer verdict.
    """
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=True)

    ctx = _ctx(
        tmp_path,
        [
            _FakeResult([_hb_row(5)]),    # below min_active_heartbeats (10)
            # No second call expected — loop skips before samples query
        ],
    )
    out = await _check_worker_process_classification(ctx)
    assert out == []


# ID: e1f2a3b4-c5d6-7890-4567-901234567890
async def test_deescalation_still_loud_no_finding(tmp_path: Path) -> None:
    """Dedicated worker, sufficient heartbeats, but 168h max > 1s → no finding."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=True)

    ctx = _ctx(
        tmp_path,
        [
            _FakeResult([_hb_row(50)]),               # plenty of heartbeats
            _sample_rows([0.3, 0.5, 1.5, 0.2, 0.8]), # 168h max = 1.5s > 1.0s gate
        ],
    )
    out = await _check_worker_process_classification(ctx)
    assert out == []


# ID: f2a3b4c5-d6e7-8901-5678-012345678901
async def test_paused_worker_skipped(tmp_path: Path) -> None:
    """Workers with metadata.status != 'active' are not evaluated."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", status="paused")

    ctx = _ctx(tmp_path, [])
    out = await _check_worker_process_classification(ctx)
    assert out == []


# ID: a3b4c5d6-e7f8-9012-6789-123456789012
async def test_two_workers_mixed_verdict(tmp_path: Path) -> None:
    """Escalation and de-escalation found simultaneously for different workers."""
    workers = tmp_path / ".intent" / "workers"
    workers.mkdir(parents=True)
    _write_worker_yaml(workers, "alpha", requires_dedicated=False)
    _write_worker_yaml(
        workers,
        "beta",
        uuid_str="22222222-3333-4444-5555-666666666666",
        requires_dedicated=True,
    )

    ctx = _ctx(
        tmp_path,
        [
            # alpha (shares_process): escalation samples
            _sample_rows([6.0, 7.0, 8.0]),
            # beta (dedicated): hb count, then samples
            _FakeResult([_hb_row(30)]),
            _sample_rows([0.1, 0.2]),
        ],
    )
    out = await _check_worker_process_classification(ctx)

    assert len(out) == 2
    verdicts = {f.context["verdict"] for f in out}
    assert verdicts == {"escalation_required", "deescalation_candidate"}


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
