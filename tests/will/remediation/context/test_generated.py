from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from will.remediation.context import ContextMixin


@pytest.fixture
# ID: d58a4c82-54fa-47ab-8f86-5501c5096e60
def context_mixin_instance():
    """Fixture that creates a minimal host instance with ContextMixin and mock _ctx."""
    mock_ctx = MagicMock()
    mock_ctx.context_service = MagicMock()
    mock_ctx.vector_store = MagicMock()
    instance = ContextMixin.__new__(ContextMixin)
    instance._ctx = mock_ctx
    return instance, mock_ctx


# ID: 13495283-44f2-4189-a89b-35681a39d91e
class TestContextMixin:
    """Tests for ContextMixin._build_context."""

    @pytest.mark.asyncio
    # ID: b2c8834a-f46e-4661-b558-c43f477c0889
    async def test_build_context_both_sources_available(self, context_mixin_instance):
        """Both call graph and semantic examples should be included."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(
            return_value="function A calls B"
        )
        mock_ctx.vector_store.search = AsyncMock(
            return_value=[
                MagicMock(payload={"source": "def correct_func(): pass"}),
                MagicMock(payload={"source": "class GoodExample: pass"}),
            ]
        )

        result = await instance._build_context("some/path.py", "error E101")

        assert "=== Call graph context ===" in result
        assert "function A calls B" in result
        assert "=== Semantic examples (correct implementations) ===" in result
        assert "def correct_func(): pass" in result
        assert "class GoodExample: pass" in result

    @pytest.mark.asyncio
    # ID: 112a7624-cf05-440b-ae06-ae19344af97e
    async def test_build_context_only_call_graph(self, context_mixin_instance):
        """Only call graph context available, no semantic examples."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(
            return_value="function A calls B"
        )
        mock_ctx.vector_store.search = AsyncMock(return_value=[])

        result = await instance._build_context("some/path.py", "error E101")

        assert "=== Call graph context ===" in result
        assert "function A calls B" in result
        assert "=== Semantic examples (correct implementations) ===" not in result

    @pytest.mark.asyncio
    # ID: 5c536759-9ca3-497c-b3f1-674d018b1dd3
    async def test_build_context_only_semantic_examples(self, context_mixin_instance):
        """Only semantic examples available, no call graph."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(return_value=None)
        mock_ctx.vector_store.search = AsyncMock(
            return_value=[
                MagicMock(payload={"source": "def good_code(): pass"}),
            ]
        )

        result = await instance._build_context("some/path.py", "error E101")

        assert "=== Call graph context ===" not in result
        assert "=== Semantic examples (correct implementations) ===" in result
        assert "def good_code(): pass" in result

    @pytest.mark.asyncio
    # ID: 8e7ac263-cd7d-487c-821d-b4fd4770b774
    async def test_build_context_both_unavailable(self, context_mixin_instance):
        """Neither source available — returns empty string."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(return_value=None)
        mock_ctx.vector_store.search = AsyncMock(return_value=[])

        result = await instance._build_context("some/path.py", "error E101")

        assert result == ""

    @pytest.mark.asyncio
    # ID: 44e6efaa-ab9c-4a7b-ab2b-d5b466fbdc89
    async def test_build_context_call_graph_raises_exception(
        self, context_mixin_instance
    ):
        """Call graph raises exception — should be caught and logged, semantic still processed."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(
            side_effect=ValueError("service unavailable")
        )
        mock_ctx.vector_store.search = AsyncMock(
            return_value=[
                MagicMock(payload={"source": "def good_code(): pass"}),
            ]
        )

        result = await instance._build_context("some/path.py", "error E101")

        assert "=== Call graph context ===" not in result
        assert "=== Semantic examples (correct implementations) ===" in result
        assert "def good_code(): pass" in result

    @pytest.mark.asyncio
    # ID: 2c7b95fb-243a-47af-9082-39145cdbd2f3
    async def test_build_context_semantic_raises_exception(
        self, context_mixin_instance
    ):
        """Semantic search raises exception — should be caught and logged, call graph still processed."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(
            return_value="function A calls B"
        )
        mock_ctx.vector_store.search = AsyncMock(
            side_effect=RuntimeError("qdrant down")
        )

        result = await instance._build_context("some/path.py", "error E101")

        assert "=== Call graph context ===" in result
        assert "function A calls B" in result
        assert "=== Semantic examples (correct implementations) ===" not in result

    @pytest.mark.asyncio
    # ID: ad4ac9de-422f-4cdc-9ee6-8fae6f622aed
    async def test_build_context_both_raise_exception(self, context_mixin_instance):
        """Both sources raise exceptions — returns empty string."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(
            side_effect=ValueError("service unavailable")
        )
        mock_ctx.vector_store.search = AsyncMock(
            side_effect=RuntimeError("qdrant down")
        )

        result = await instance._build_context("some/path.py", "error E101")

        assert result == ""

    @pytest.mark.asyncio
    # ID: 47787c97-6d1e-497e-b26f-4f3c8734f2be
    async def test_build_context_semantic_hits_with_null_payload(
        self, context_mixin_instance
    ):
        """Semantic hits with None payload should be filtered out."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(return_value=None)
        mock_ctx.vector_store.search = AsyncMock(
            return_value=[
                MagicMock(payload=None),
                MagicMock(payload={"source": "valid source code"}),
                MagicMock(payload=None),
            ]
        )

        result = await instance._build_context("some/path.py", "error E101")

        assert "=== Semantic examples (correct implementations) ===" in result
        assert "valid source code" in result
        assert result.count("valid source code") == 1

    @pytest.mark.asyncio
    # ID: c2544aae-d029-4e09-8b47-0fb53cc1d9e8
    async def test_build_context_empty_violations_summary(self, context_mixin_instance):
        """Empty violations_summary should not cause errors."""
        instance, mock_ctx = context_mixin_instance
        mock_ctx.context_service.get_context_for_file = AsyncMock(
            return_value="call graph info"
        )
        mock_ctx.vector_store.search = AsyncMock(
            return_value=[
                MagicMock(payload={"source": "example code"}),
            ]
        )

        result = await instance._build_context("some/path.py", "")

        assert "=== Call graph context ===" in result
        assert "=== Semantic examples (correct implementations) ===" in result
