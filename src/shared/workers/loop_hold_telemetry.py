# src/shared/workers/loop_hold_telemetry.py
"""
ADR-081 Step 3a-telemetry — structured sink for asyncio slow-callback warnings.

When the daemon enables `loop.set_debug(True)` (ADR-081 Step 0), the asyncio
event loop emits a `logger.warning` on the "asyncio" logger every time a
single handle executes for longer than `slow_callback_duration`. The
warning's repr carries the running task's `name='<stem>_worker'` attribute,
which the daemon assigns at task-creation time.

This module restructures that emission stream into machine-readable
`loop_hold.sample::<stem>` blackboard entries — the data source the
Step 3b drift detector consumes.

Two collaborators:

- `SlowCallbackBlackboardHandler` — a `logging.Handler` subclass installed
  on the "asyncio" logger. `emit()` runs synchronously on the asyncio hot
  path, so it MUST NOT block and MUST NOT raise. It parses the slow-callback
  message into a structured sample and pushes it (non-blocking) onto an
  asyncio queue.

- `drain_loop_hold_samples()` — a long-running coroutine spawned as a
  daemon task. It awaits samples from the queue and posts each to the
  blackboard via the matching worker's `post_observation()`. Decoupling
  the post from `emit()` keeps the measurement channel from blocking the
  loop it measures.

The queue is bounded — backpressure manifests as silent sample drops in
`emit()` rather than back-pressuring the loop. Acceptable: slow-callback
warnings are sparse compared to general loop activity, and a missed
sample is cheaper than a measurement-induced perf regression.

LAYER: shared.workers — telemetry infrastructure. No file writes, no
direct DB access — posts via Worker.post_observation which routes
through the standard blackboard path. Imported by cli.commands.daemon.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.workers.base import Worker


logger = getLogger(__name__)


# The slow-callback warning's handle repr embeds `name='<task name>'` for
# task-wrapping handles. Workers are named `<stem>_worker` by the daemon at
# create_task time (see cli.commands.daemon._run_daemon_locked), so the
# captured group gives us the task name; the `_worker` suffix is stripped
# downstream to recover the YAML stem.
_TASK_NAME_RE = re.compile(r"name='([^']+)'")

# Queue cap — drop samples beyond this rather than blocking emit(). The
# heaviest realistic flux is ~1 slow callback per cycle * ~10 workers per
# process * 1 cycle/second worst case = ~10/s. 1024 buys ~2 minutes of
# headroom before drop; the drain coroutine empties it as fast as the
# blackboard accepts inserts.
_QUEUE_MAXSIZE = 1024


# ID: 5e5f1c2a-3b4d-4c5e-9f8a-0b1c2d3e4f50
class SlowCallbackBlackboardHandler(logging.Handler):
    """Subscribes asyncio slow-callback warnings to a queued blackboard sink.

    Installed on the ``asyncio`` logger by the daemon at startup when
    ``loop.set_debug(True)`` is enabled (per ADR-081 Step 0). ``emit()`` is
    on the asyncio hot path — it MUST NOT block and MUST NOT raise.

    The handler parses each warning record into a structured sample and
    pushes it (non-blocking) onto the queue. A separate drain coroutine
    posts samples to the blackboard. If the queue is full, samples are
    dropped silently — preferable to blocking the loop with backpressure
    from the measurement channel.
    """

    # ID: 8c2d4f6a-9e1b-4a3c-bf5d-2e7f0a1b3c4d
    def __init__(self, sample_queue: asyncio.Queue[dict[str, Any]]) -> None:
        super().__init__()
        self._queue = sample_queue

    # ID: a1b2c3d4-5e6f-7a8b-9c0d-1e2f3a4b5c6d
    def emit(self, record: logging.LogRecord) -> None:
        try:
            # The slow-callback warning logs with `record.args = (handle, duration)`
            # via `logger.warning("Executing %s took %.3f seconds", handle, dur)`
            # (CPython asyncio/base_events.py). Anything else on the asyncio
            # logger gets ignored.
            args = record.args
            if not args or not isinstance(args, tuple) or len(args) < 2:
                return
            try:
                duration_sec = float(args[1])  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return
            handle_repr = str(args[0])
            m = _TASK_NAME_RE.search(handle_repr)
            if not m:
                # Slow callback wasn't a named task — could be an internal
                # asyncio handle (e.g. a timer). Skip silently; this is not
                # a worker-attributable sample.
                return
            task_name = m.group(1)
            stem = task_name.removesuffix("_worker")
            sample = {
                "stem": stem,
                "duration_sec": duration_sec,
                "handle_repr": handle_repr,
                "ts": datetime.now(UTC).isoformat(),
            }
            try:
                self._queue.put_nowait(sample)
            except asyncio.QueueFull:
                # Drop the sample silently. The drain coroutine will catch
                # up on the next free slot; we never block emit() on the
                # hot path waiting for blackboard capacity.
                pass
        except Exception:
            # Last-ditch safety net. A logging handler exception on the
            # asyncio hot path would inject latency back into the loop it's
            # measuring — never propagate.
            pass


# ID: c0d1e2f3-a4b5-c6d7-e8f9-0a1b2c3d4e5f
def make_sample_queue() -> asyncio.Queue[dict[str, Any]]:
    """Construct the bounded queue the handler pushes into.

    Kept as a factory so the daemon can construct it in the same coroutine
    that owns the drain task — `asyncio.Queue` binds to the current event
    loop at construction time.
    """
    return asyncio.Queue(maxsize=_QUEUE_MAXSIZE)


# ID: d1e2f3a4-b5c6-d7e8-f9a0-b1c2d3e4f5a6
async def drain_loop_hold_samples(
    sample_queue: asyncio.Queue[dict[str, Any]],
    workers_by_stem: dict[str, Worker],
) -> None:
    """Drain the slow-callback sample queue to the blackboard.

    Posts each sample as a ``loop_hold.sample::<stem>`` observability entry
    under the matching worker's UUID, status ``abandoned`` — the terminal
    status the Worker.post_observation contract reserves for per-event
    records that recur on the next detection (the same shape the
    ``*.yield.receipt`` pattern uses; ADR-069 / observability-TTL recon).

    Cancellation-safe: an outer ``asyncio.CancelledError`` exits the loop
    cleanly without losing buffered samples. Per-sample errors are logged
    but never propagate — telemetry failure must not bring down the daemon.
    """
    logger.info(
        "loop_hold telemetry: drain coroutine started "
        "(%d worker(s) registered for attribution)",
        len(workers_by_stem),
    )
    posted = 0
    skipped_unknown_stem = 0
    while True:
        try:
            sample = await sample_queue.get()
        except asyncio.CancelledError:
            logger.info(
                "loop_hold telemetry: drain coroutine cancelled "
                "(posted=%d, skipped_unknown_stem=%d)",
                posted,
                skipped_unknown_stem,
            )
            raise
        stem = sample["stem"]
        worker = workers_by_stem.get(stem)
        if worker is None:
            # Task name didn't map to a registered worker. Could be the
            # _run_one_shot_loop wrapper task (its name carries the stem
            # but the wrapper itself isn't the Worker instance), or an
            # internal asyncio task. Either way, no UUID to attribute to —
            # drop the sample.
            skipped_unknown_stem += 1
            continue
        try:
            await worker.post_observation(
                subject=f"loop_hold.sample::{stem}",
                payload={
                    "duration_sec": sample["duration_sec"],
                    "handle_repr": sample["handle_repr"],
                    "ts": sample["ts"],
                },
                status="abandoned",
            )
            posted += 1
        except Exception as e:
            # Telemetry post failure must not bring down the daemon or the
            # drain loop. Log and continue — the next sample is more
            # important than this one's persistence.
            logger.warning(
                "loop_hold telemetry: post failed for stem=%s: %s",
                stem,
                e,
            )
