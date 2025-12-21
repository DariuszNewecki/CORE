# src/shared/utils/parallel_processor.py

"""
Provides a reusable, throttled parallel processor for running async tasks
concurrently.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)
T = TypeVar("T")
R = TypeVar("R")


# ID: 08955ac4-99b0-4bac-b3e4-3c9deb938e68
class ThrottledParallelProcessor:
    """
    A dedicated executor for running a worker function over a list of items
    in parallel, with concurrency limited by the constitution.
    """

    def __init__(self, description: str = "Processing items..."):
        self.concurrency_limit = settings.CORE_MAX_CONCURRENT_REQUESTS
        self.description = description
        logger.info(
            "ThrottledParallelProcessor initialized with concurrency limit: %s",
            self.concurrency_limit,
        )

    async def _process_items_async(
        self, items: list[T], worker_fn: Callable[[T], Awaitable[R]]
    ) -> list[R]:
        semaphore = asyncio.Semaphore(self.concurrency_limit)
        results: list[R] = []

        async def _worker(item: T) -> R:
            async with semaphore:
                return await worker_fn(item)

        tasks = [asyncio.create_task(_worker(item)) for item in items]

        logger.debug("%s", self.description)
        for task in asyncio.as_completed(tasks):
            results.append(await task)

        return results

    # ID: d64f09ac-d05d-4a32-ad5d-87bf95d0efcf
    async def run_async(
        self, items: list[T], worker_fn: Callable[[T], Awaitable[R]]
    ) -> list[R]:
        return await self._process_items_async(items, worker_fn)
