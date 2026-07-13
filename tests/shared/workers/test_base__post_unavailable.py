"""Tests for Worker.post_unavailable — the instrument-unavailable taxonomy
leg (#765/T1.3).

"Couldn't look" must be recorded distinctly from "genuinely clean". This
helper stores it as an `indeterminate` observation (resolution_mechanism=
human, stamped by the publisher), reusing existing machinery rather than a
new status. Unit-level: the underlying post_observation is mocked, so no DB.
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import AsyncMock

from shared.workers.base import Worker


class _MinimalWorker(Worker):
    declaration_name: ClassVar[str] = "db_sync_worker"

    async def run(self) -> None:
        return


async def test_post_unavailable_posts_indeterminate_observation() -> None:
    worker = _MinimalWorker()
    worker._blackboard.post_observation = AsyncMock(return_value="entry-id")

    await worker.post_unavailable(
        subject="some_sensor.instrument_unavailable",
        reason="source root not found at /repo/src",
    )

    worker._blackboard.post_observation.assert_awaited_once()
    call = worker._blackboard.post_observation.await_args
    assert call.args[0] == "some_sensor.instrument_unavailable"
    assert call.kwargs["status"] == "indeterminate"
    payload = call.args[1]
    assert payload["instrument_result"] == "unavailable"
    assert payload["reason"] == "source root not found at /repo/src"


async def test_post_unavailable_merges_detail() -> None:
    worker = _MinimalWorker()
    worker._blackboard.post_observation = AsyncMock(return_value="entry-id")

    await worker.post_unavailable(
        subject="s.instrument_unavailable",
        reason="db down",
        detail={"host": "192.168.20.23", "attempt": 3},
    )

    payload = worker._blackboard.post_observation.await_args.args[1]
    assert payload["instrument_result"] == "unavailable"
    assert payload["reason"] == "db down"
    assert payload["host"] == "192.168.20.23"
    assert payload["attempt"] == 3


def test_post_unavailable_increments_cycle_post_count() -> None:
    """post_unavailable must count toward the silence invariant like any
    other blackboard post."""
    import asyncio

    worker = _MinimalWorker()
    worker._blackboard.post_observation = AsyncMock(return_value="entry-id")

    before = worker._cycle_post_count
    asyncio.run(
        worker.post_unavailable(subject="s.instrument_unavailable", reason="x")
    )
    assert worker._cycle_post_count == before + 1
