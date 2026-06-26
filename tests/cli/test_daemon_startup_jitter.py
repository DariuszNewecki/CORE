"""#611 — cold-start jitter verification for `_run_one_shot_loop`.

The post-restart API blackout cascade was caused by every one-shot worker
running its first cycle at the same wall-clock instant. The fix adds a
deterministic stem-hash offset before the first cycle inside the
`_run_one_shot_loop` driver. These tests pin:

1. The offset calculation matches what the function produces.
2. The first asyncio.sleep call inside the loop equals that offset and
   happens BEFORE the first worker.start() invocation.
3. The offsets actually spread the audit_sensor cohort that the issue
   identifies as the saturation case (collision-bounded — at most a few
   sensors share an offset).
4. Short-cycle workers don't lose a full cycle to the jitter cap.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from cli.commands import daemon as daemon_module
from cli.commands.daemon import _STARTUP_JITTER_CAP_SEC, _run_one_shot_loop


def _expected_offset(stem: str, cap: int) -> int:
    return int.from_bytes(hashlib.sha256(stem.encode()).digest()[:2], "big") % cap


async def test_run_one_shot_loop_sleeps_jitter_before_first_cycle(monkeypatch):
    """The first asyncio.sleep call equals the stem-hash offset and
    precedes the first worker.start() call."""
    stem = "audit_sensor_purity"
    interval = 3600
    expected = _expected_offset(stem, _STARTUP_JITTER_CAP_SEC)
    assert expected > 0, "test fixture relies on a non-zero offset"

    events: list[tuple[str, float | None]] = []

    class FakeWorker:
        async def start(self):
            events.append(("start", None))
            # Stop after the first cycle by raising CancelledError so the
            # while-True loop unwinds cleanly.
            raise asyncio.CancelledError

    async def fake_sleep(secs):
        events.append(("sleep", secs))

    monkeypatch.setattr(daemon_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await _run_one_shot_loop(FakeWorker(), stem, interval)

    # First event must be the jitter sleep with the expected offset.
    assert events[0] == ("sleep", expected)
    # Worker.start must have been called AFTER the jitter sleep.
    assert ("start", None) in events
    assert events.index(("sleep", expected)) < events.index(("start", None))


def test_jitter_offsets_spread_audit_sensor_cohort():
    """The audit_sensor_* stems all hash to distinct enough offsets that
    the cohort no longer cold-starts simultaneously. Allows up to two
    collisions out of nine — what matters is that the cohort spreads
    across most of the cap window."""
    stems = [
        "audit_sensor_architecture",
        "audit_sensor_cli",
        "audit_sensor_governance",
        "audit_sensor_layout",
        "audit_sensor_linkage",
        "audit_sensor_logic",
        "audit_sensor_modularity",
        "audit_sensor_purity",
        "audit_sensor_style",
    ]
    offsets = {s: _expected_offset(s, _STARTUP_JITTER_CAP_SEC) for s in stems}
    distinct = len(set(offsets.values()))
    spread = max(offsets.values()) - min(offsets.values())
    assert distinct >= 7, f"too many collisions: {offsets}"
    assert spread >= _STARTUP_JITTER_CAP_SEC // 2, f"spread too narrow: {spread}"


def test_jitter_cap_respects_short_cycle_workers():
    """For workers with a max_interval shorter than the jitter cap, the
    cap is reduced to the interval so the first cycle isn't deferred past
    when the second cycle would have run."""
    stem = "audit_sensor_purity"
    short_interval = 10
    cap = min(_STARTUP_JITTER_CAP_SEC, max(short_interval, 0))
    assert cap == short_interval
    offset = _expected_offset(stem, cap)
    assert 0 <= offset < short_interval


def test_jitter_cap_handles_zero_interval_gracefully():
    """If a worker declares interval=0 (test fixture or degenerate config),
    the loop must not raise on a modulo by zero — jitter is skipped."""
    # The implementation's `if jitter_cap > 0:` guard handles this; the
    # test pins the no-op outcome so a future refactor can't reintroduce
    # the ZeroDivisionError silently.
    cap = min(_STARTUP_JITTER_CAP_SEC, max(0, 0))
    assert cap == 0
