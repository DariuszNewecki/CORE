"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/constitutional_monitor.py
- Symbol: KnowledgeGraphBuilderProtocol
- Status: 2 tests passed, some failed
- Passing tests: test_build_and_sync_is_async_and_returns_none, test_concrete_implementation_with_side_effect
- Generated: 2026-01-11 01:20:34
"""

import pytest

from mind.governance.constitutional_monitor import KnowledgeGraphBuilderProtocol


@pytest.mark.asyncio
async def test_build_and_sync_is_async_and_returns_none():
    """Test that a concrete class implementing the protocol can be awaited and returns None."""

    class ConcreteBuilder(KnowledgeGraphBuilderProtocol):

        async def build_and_sync(self) -> None:
            return None

    builder = ConcreteBuilder()
    result = await builder.build_and_sync()
    assert result is None


@pytest.mark.asyncio
async def test_concrete_implementation_with_side_effect():
    """Test a concrete implementation that performs an operation."""
    state = []

    class ConcreteBuilder(KnowledgeGraphBuilderProtocol):

        async def build_and_sync(self) -> None:
            state.append("synced")

    builder = ConcreteBuilder()
    assert state == []
    result = await builder.build_and_sync()
    assert result is None
    assert state == ["synced"]
