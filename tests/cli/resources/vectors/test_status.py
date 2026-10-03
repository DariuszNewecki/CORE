"""Tests for ``core-admin vectors status`` — Qdrant health for this installation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import typer

from cli.resources.vectors import status as status_mod


def _ctx(get_collections: AsyncMock) -> SimpleNamespace:
    qdrant = SimpleNamespace(client=SimpleNamespace(get_collections=get_collections))
    return SimpleNamespace(obj=SimpleNamespace(qdrant_service=qdrant))


@pytest.mark.asyncio
async def test_lists_collections() -> None:
    collections = SimpleNamespace(collections=[SimpleNamespace(name="core-code")])
    get = AsyncMock(return_value=collections)
    await status_mod.status_vectors.__wrapped__(ctx=_ctx(get))
    get.assert_awaited_once()


@pytest.mark.asyncio
async def test_connection_failure_exits_1() -> None:
    get = AsyncMock(side_effect=RuntimeError("down"))
    with pytest.raises(typer.Exit) as exc:
        await status_mod.status_vectors.__wrapped__(ctx=_ctx(get))
    assert exc.value.exit_code == 1


def test_registered_on_core_admin() -> None:
    from cli.resources.vectors import app

    assert "status" in {c.name for c in app.registered_commands}
