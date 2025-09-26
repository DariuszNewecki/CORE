# src/shared/utils/parallel_processor.py
"""
Provides a reusable, throttled parallel processor for running async tasks
concurrently with a progress bar, governed by a constitutional limit.
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


# ID: c88b0e64-3e38-4fef-983e-cd59281e53e0
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
        log.info(
            f"ThrottledParallelProcessor initialized with concurrency limit: "
            f"{self.concurrency_limit}"
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

        # Use track for a visual progress bar in the console
        for task in track(
            asyncio.as_completed(tasks), description=self.description, total=len(items)
        ):
            results.append(await task)

        return results

    # --- START: THE DEFINITIVE FIX ---
    # ID: dee1af19-41c8-49c6-ba11-a109746795b7
    async def run_async(
        self, items: List[T], worker_fn: Callable[[T], Awaitable[R]]
    ) -> List[R]:
        """
        Asynchronous entry point to run the worker over all items.
        To be used when called from an already-running async function.
        """
        return await self._process_items_async(items, worker_fn)

    # ID: 466317ce-4caa-4c49-a466-5389d9c25874
    def run_sync(
        self, items: List[T], worker_fn: Callable[[T], Awaitable[R]]
    ) -> List[R]:
        """
        Synchronous entry point to run the async worker over all items.
        This will start and manage its own asyncio event loop.
        """
        return asyncio.run(self._process_items_async(items, worker_fn))

    # --- END: THE DEFINITIVE FIX ---
