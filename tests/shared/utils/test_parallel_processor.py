# tests/shared/utils/test_parallel_processor.py
"""Tests for parallel_processor module."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from shared.utils.parallel_processor import ThrottledParallelProcessor


class TestThrottledParallelProcessor:
    """Tests for ThrottledParallelProcessor class."""

    @pytest.mark.asyncio
    async def test_processes_items_async(self):
        """Test processing items asynchronously."""
        processor = ThrottledParallelProcessor(description="Test processing")
        items = [1, 2, 3, 4, 5]

        async def worker(item: int) -> int:
            await asyncio.sleep(0.01)
            return item * 2

        results = await processor.run_async(items, worker)

        assert len(results) == 5
        assert set(results) == {2, 4, 6, 8, 10}

    def test_processes_items_sync(self):
        """Test processing items synchronously."""
        processor = ThrottledParallelProcessor(description="Test sync")
        items = [1, 2, 3]

        async def worker(item: int) -> int:
            return item + 10

        results = processor.run_sync(items, worker)

        assert len(results) == 3
        assert set(results) == {11, 12, 13}

    @pytest.mark.asyncio
    async def test_respects_concurrency_limit(self):
        """Test that concurrency limit is respected."""
        with patch("shared.config.settings.CORE_MAX_CONCURRENT_REQUESTS", 2):
            processor = ThrottledParallelProcessor()
            assert processor.concurrency_limit == 2

            items = [1, 2, 3, 4]
            concurrent_count = 0
            max_concurrent = 0

            async def worker(item: int) -> int:
                nonlocal concurrent_count, max_concurrent
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.05)
                concurrent_count -= 1
                return item

            results = await processor.run_async(items, worker)

            assert len(results) == 4
            # With limit of 2, we should never exceed 2 concurrent tasks
            assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_handles_empty_list(self):
        """Test processing empty list."""
        processor = ThrottledParallelProcessor()

        async def worker(item: int) -> int:
            return item

        results = await processor.run_async([], worker)

        assert results == []

    @pytest.mark.asyncio
    async def test_handles_exceptions_in_worker(self):
        """Test that exceptions in worker are propagated."""
        processor = ThrottledParallelProcessor()
        items = [1, 2, 3]

        async def failing_worker(item: int) -> int:
            if item == 2:
                raise ValueError("Test error")
            return item

        with pytest.raises(ValueError, match="Test error"):
            await processor.run_async(items, failing_worker)

    @pytest.mark.asyncio
    async def test_worker_receives_correct_items(self):
        """Test that worker function receives all items."""
        processor = ThrottledParallelProcessor()
        items = ["a", "b", "c"]
        received_items = []

        async def tracking_worker(item: str) -> str:
            received_items.append(item)
            return item.upper()

        results = await processor.run_async(items, tracking_worker)

        assert set(received_items) == {"a", "b", "c"}
        assert set(results) == {"A", "B", "C"}

    def test_custom_description(self):
        """Test custom description is stored."""
        description = "Custom processing message"
        processor = ThrottledParallelProcessor(description=description)

        assert processor.description == description

    @pytest.mark.asyncio
    async def test_maintains_result_count(self):
        """Test that number of results matches number of items."""
        processor = ThrottledParallelProcessor()
        items = list(range(10))

        async def worker(item: int) -> int:
            await asyncio.sleep(0.001)
            return item * item

        results = await processor.run_async(items, worker)

        assert len(results) == len(items)

    def test_sync_entry_point_creates_event_loop(self):
        """Test that run_sync properly manages event loop."""
        processor = ThrottledParallelProcessor()
        items = [1, 2]

        async def worker(item: int) -> int:
            return item + 100

        # This should work even without an existing event loop
        results = processor.run_sync(items, worker)

        assert len(results) == 2
        assert set(results) == {101, 102}

    @pytest.mark.asyncio
    async def test_worker_with_complex_types(self):
        """Test processing with complex object types."""
        processor = ThrottledParallelProcessor()
        items = [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]

        async def worker(item: dict) -> str:
            await asyncio.sleep(0.01)
            return f"{item['id']}:{item['value']}"

        results = await processor.run_async(items, worker)

        assert len(results) == 2
        assert set(results) == {"1:a", "2:b"}
