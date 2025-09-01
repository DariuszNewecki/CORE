# src/shared/utils/parallel_processor.py
"""
Provides a reusable, throttled parallel processor for running async tasks concurrently with a progress bar, governed by a constitutional limit.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List, TypeVar

from rich.progress import track

from shared.config import settings
from shared.logger import getLogger

log = getLogger("parallel_processor")
T = TypeVar("T")
R = TypeVar("R")


# CAPABILITY: shared.throttled_parallel_processing
class ThrottledParallelProcessor:
    """
    A dedicated executor for running a worker function over a list of items
    in parallel, with concurrency limited by the constitution.
    """

    def __init__(self, description: str = "Processing items..."):
        """
        Initializes the processor.
        Args:
            description: The description to show in the progress bar.
        """
        self.concurrency_limit = settings.CORE_MAX_CONCURRENT_REQUESTS
        self.description = description
        log.info(
            f"ThrottledParallelProcessor initialized with concurrency limit: {self.concurrency_limit}"
        )

    async def _process_items_async(
        self, items: List[T], worker_fn: Callable[[T], Awaitable[R]]
    ) -> List[R]:
        """The core async logic for processing items in parallel."""
        semaphore = asyncio.Semaphore(self.concurrency_limit)
        results = []

        async def _worker(item: T) -> R:
            async with semaphore:
                return await worker_fn(item)

        tasks = [asyncio.create_task(_worker(item)) for item in items]

        for task in track(
            asyncio.as_completed(tasks), description=self.description, total=len(items)
        ):
            results.append(await task)

        return results

    def run(self, items: List[T], worker_fn: Callable[[T], Awaitable[R]]) -> List[R]:
        """
        Synchronous entry point to run the async worker over all items.

        Args:
            items: A list of items to process.
            worker_fn: An async function that takes one item and returns a result.

        Returns:
            A list of results from the worker function.
        """
        return asyncio.run(self._process_items_async(items, worker_fn))
