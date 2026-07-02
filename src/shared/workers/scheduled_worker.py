# src/shared/workers/scheduled_worker.py
"""
ScheduledWorker — Constitutional base for self-scheduling (Model B) workers.

A ScheduledWorker owns its own loop: the Sanctuary calls ``run_loop()`` once
on bootstrap and the worker cycles indefinitely, sleeping for the remainder of
``max_interval`` after each call to ``run()``.  This is distinct from the
one-shot Model A contract enforced by ``Worker.start()``.

Constitutional obligations inherited from Worker:
- Identity and registration (UUID from .intent/workers/ declaration)
- Blackboard history: every ``run()`` cycle MUST post at least one entry
- Scope: declared in .intent/workers/; subclasses declare what they may touch

Scheduling parameters are sourced from the worker's .intent/ declaration at
``mandate.schedule``.  A missing ``max_interval`` is a declaration defect and
raises ``WorkerConfigurationError`` rather than silently defaulting — fail-closed
per constitutional principle.

LAYER: shared/workers — infrastructure shared by Will (sensing) and Body (acting).
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker, WorkerConfigurationError


logger = getLogger(__name__)


# ID: 21aa21f2-c4ba-4d6c-82f6-fa4a419c20fd
class ScheduledWorker(Worker, ABC):
    """Base class for workers that manage their own scheduling loop (Model B).

    Subclasses must still implement ``run()`` — the single unit of constitutional
    work executed each cycle.  The scheduling scaffold (register, loop, sleep,
    error handling) is provided here so subclasses carry only domain logic.

    Workers that need one-time service initialization before the first cycle
    should override ``_before_loop()`` rather than ``run_loop()`` — overriding
    ``run_loop()`` re-opens the scaffold to per-worker drift.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        if "max_interval" not in schedule:
            raise WorkerConfigurationError(
                f"Worker declaration '{self.declaration_name}' is missing "
                "mandate.schedule.max_interval — required for ScheduledWorker."
            )
        self._max_interval: int = int(schedule["max_interval"])
        self._glide_off: int = int(
            schedule.get("glide_off", max(int(self._max_interval * 0.10), 10))
        )

    # ID: 11f3de4a-628e-4d4d-933d-8a337853b819
    async def run_loop(self) -> None:
        """Continuous self-scheduling loop.  Sanctuary calls this once on bootstrap.

        Registers the worker, runs the ``_before_loop`` hook, then cycles:
        ``run()`` → catch exceptions → sleep for remainder of ``max_interval``.
        Never raises — exceptions are caught, logged, and posted to the blackboard.
        """
        logger.info(
            "%s: starting loop (max_interval=%ds, glide_off=%ds)",
            self._worker_name,
            self._max_interval,
            self._glide_off,
        )
        await self._register()
        await self._before_loop()

        while True:
            cycle_start = time.monotonic()
            try:
                await self.run()
            except Exception as exc:
                logger.error(
                    "%s: cycle failed: %s", self._worker_name, exc, exc_info=True
                )
                try:
                    await self._blackboard._post_entry(
                        entry_type="report",
                        subject=f"{self.declaration_name}.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception(
                        "%s: failed to post cycle-error report", self._worker_name
                    )
            elapsed = time.monotonic() - cycle_start
            await asyncio.sleep(max(self._max_interval - elapsed, 0))

    async def _before_loop(self) -> None:
        """Called once after registration, before the first cycle.

        Override for pre-loop service initialization (e.g. lazy-loading a
        cognitive service).  The default implementation is a no-op.
        """
