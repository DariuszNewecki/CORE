"""#1271: a one-shot worker whose first start fails retries soon.

The 2026-10-23 recovery drill restored a VM whose daemon started while
PostgreSQL was still recovering. A one-shot worker that could not register
then waited a whole interval (7 to 60 minutes) before trying again. Until it
has registered once, it now retries after 5s, backing off to 300s; after
that, a failed cycle waits the interval as before.
"""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from cli.commands import daemon as daemon_module
from cli.commands.daemon import _run_one_shot_loop


class _Worker:
    def __init__(self, fail_first: int, stop_after: int) -> None:
        self.registered = False
        self.calls = 0
        self.fail_first = fail_first
        self.stop_after = stop_after

    async def start(self) -> None:
        self.calls += 1
        if self.calls > self.stop_after:
            raise asyncio.CancelledError
        if self.calls <= self.fail_first:
            raise ConnectionRefusedError("Connect call failed ('127.0.0.1', 5432)")
        self.registered = True


async def _sleeps(monkeypatch, worker: _Worker, interval: int) -> list[float]:
    slept: list[float] = []

    async def fake_sleep(secs):
        slept.append(secs)

    no_jitter = dataclasses.replace(daemon_module._CFG, startup_jitter_cap_sec=0)
    monkeypatch.setattr(daemon_module, "_CFG", no_jitter)
    monkeypatch.setattr(daemon_module.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await _run_one_shot_loop(worker, "quality_ingest_worker", interval)
    return slept


async def test_a_first_start_that_fails_is_retried_soon_with_backoff(
    monkeypatch,
) -> None:
    slept = await _sleeps(monkeypatch, _Worker(fail_first=3, stop_after=5), 3600)
    assert [round(s) for s in slept] == [5, 10, 20, 3600, 3600]


async def test_the_backoff_stops_at_300_seconds(monkeypatch) -> None:
    slept = await _sleeps(monkeypatch, _Worker(fail_first=8, stop_after=8), 3600)
    assert [round(s) for s in slept] == [5, 10, 20, 40, 80, 160, 300, 300]


async def test_after_registering_a_failed_cycle_waits_the_interval(
    monkeypatch,
) -> None:
    class _Flaky(_Worker):
        async def start(self) -> None:
            self.calls += 1
            if self.calls > 3:
                raise asyncio.CancelledError
            self.registered = True
            if self.calls == 2:
                raise RuntimeError("a cycle failed after registering")

    slept = await _sleeps(monkeypatch, _Flaky(0, 3), 600)
    assert [round(s) for s in slept] == [600, 600, 600]


async def test_a_worker_without_the_flag_keeps_the_interval(monkeypatch) -> None:
    class _Plain:
        calls = 0

        async def start(self) -> None:
            self.calls += 1
            if self.calls > 2:
                raise asyncio.CancelledError
            raise RuntimeError("down")

    slept = await _sleeps(monkeypatch, _Plain(), 600)  # type: ignore[arg-type]
    assert [round(s) for s in slept] == [600, 600]
