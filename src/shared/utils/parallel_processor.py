# src/shared/utils/parallel_processor.py

"""
Provides a reusable, throttled parallel processor for running async tasks
concurrently.

UI STANDARDS UPDATE:
Switched from Progress Bar (track) to Spinner (status) to comply with
workflow_patterns.yaml visual standards.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from rich.console import Console

from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)
console = Console()
T = TypeVar("T")
R = TypeVar("R")


# ID: 08955ac4-99b0-4bac-b3e4-3c9deb938e68
class ThrottledParallelProcessor:
    """
    A dedicated executor for running a worker function over a list of items
    in parallel, with concurrency limited by the constitution.
    """

    def __init__(self, description: str = "Processing items..."):
        """
        Initializes the processor.
        """
        self.concurrency_limit = settings.CORE_MAX_CONCURRENT_REQUESTS
        self.description = description
        logger.info(
            "ThrottledParallelProcessor initialized with concurrency limit: %s",
            self.concurrency_limit,
        )

    async def _process_items_async(
        self, items: list[T], worker_fn: Callable[[T], Awaitable[R]]
    ) -> list[R]:
        """The core async logic for processing items in parallel."""
        semaphore = asyncio.Semaphore(self.concurrency_limit)
        results = []

        async def _worker(item: T) -> R:
            async with semaphore:
                return await worker_fn(item)

        tasks = [asyncio.create_task(_worker(item)) for item in items]

        logger.info("%s", self.description)
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)

        return results

    # ID: d64f09ac-d05d-4a32-ad5d-87bf95d0efcf
    async def run_async(
        self, items: list[T], worker_fn: Callable[[T], Awaitable[R]]
    ) -> list[R]:
        """
        Asynchronous entry point to run the worker over all items.
        """
        return await self._process_items_async(items, worker_fn)

    # ID: 52b37f99-ccf6-44fe-bdae-9286f5330482
    def run_sync(
        self, items: list[T], worker_fn: Callable[[T], Awaitable[R]]
    ) -> list[R]:
        """
        Synchronous entry point to run the async worker over all items.
        """
        return asyncio.run(self._process_items_async(items, worker_fn))
