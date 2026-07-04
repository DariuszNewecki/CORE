# tests/body/services/test_capability_tagging_dispatch.py
"""Tests for CapabilityTaggingService (ADR-064 Body-layer dispatch facade)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from body.services.capability_tagging_dispatch import CapabilityTaggingService


class TestCapabilityTaggingService:
    """CapabilityTaggingService wraps an injected callable — no will.* import."""

    @pytest.mark.asyncio
    async def test_run_delegates_to_injected_callable(self) -> None:
        main_async_mock = AsyncMock()
        svc = CapabilityTaggingService(main_async_mock)

        session_factory = MagicMock()
        cognitive_service = MagicMock()
        knowledge_service = MagicMock()

        await svc.run(
            session_factory=session_factory,
            cognitive_service=cognitive_service,
            knowledge_service=knowledge_service,
            write=True,
            dry_run=False,
            limit=5,
        )

        main_async_mock.assert_awaited_once_with(
            session_factory=session_factory,
            cognitive_service=cognitive_service,
            knowledge_service=knowledge_service,
            write=True,
            dry_run=False,
            limit=5,
        )

    @pytest.mark.asyncio
    async def test_run_defaults(self) -> None:
        main_async_mock = AsyncMock()
        svc = CapabilityTaggingService(main_async_mock)

        await svc.run(
            session_factory=MagicMock(),
            cognitive_service=MagicMock(),
            knowledge_service=MagicMock(),
        )

        _call_kwargs = main_async_mock.call_args.kwargs
        assert _call_kwargs["write"] is False
        assert _call_kwargs["dry_run"] is False
        assert _call_kwargs["limit"] == 0

    def test_construction_accepts_any_callable(self) -> None:
        sync_fn = MagicMock()
        svc = CapabilityTaggingService(sync_fn)
        assert svc._fn is sync_fn
