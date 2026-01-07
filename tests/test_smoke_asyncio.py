# tests/test_smoke_asyncio.py

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_smoke_asyncio_strict_event_loop_is_operational() -> None:
    """
    Validates pytest-asyncio strict mode is working and the event loop is usable.
    """
    await asyncio.sleep(0)
    assert True
