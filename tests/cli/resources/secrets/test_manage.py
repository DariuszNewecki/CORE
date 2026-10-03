"""Tests for ``core-admin secrets`` — installation secrets, operator surface.

The secret store holds this installation's credentials (LLM provider keys), so
its CLI belongs to core-admin (ADR-146 amendment 2026-10-03). The database
session and SecretsService are replaced with fakes; nothing touches a real DB.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.resources.secrets import manage
from shared.exceptions import SecretNotFoundError


def _patched(service: MagicMock):
    @asynccontextmanager
    async def _session():
        yield MagicMock()

    return (
        patch.object(manage, "get_session", _session),
        patch.object(manage, "get_secrets_service", AsyncMock(return_value=service)),
    )


@pytest.mark.asyncio
async def test_list_returns_key_names_only() -> None:
    svc = MagicMock()
    svc.list_secrets = AsyncMock(
        return_value=[{"key": "anthropic.api_key", "created_at": "2026-10-03"}]
    )
    p1, p2 = _patched(svc)
    with p1, p2:
        result = await manage._list_secrets_internal()
    assert result.ok
    assert result.data == {"count": 1, "secrets": ["anthropic.api_key"]}


@pytest.mark.asyncio
async def test_get_missing_secret_is_not_ok() -> None:
    svc = MagicMock()
    svc.get_secret = AsyncMock(side_effect=SecretNotFoundError("nope"))
    p1, p2 = _patched(svc)
    with p1, p2:
        result = await manage._get_internal("nope", show=False)
    assert not result.ok
    assert result.data == {"key": "nope", "exists": False}


@pytest.mark.asyncio
async def test_set_with_force_skips_existence_check() -> None:
    svc = MagicMock()
    svc.get_secret = AsyncMock()
    svc.set_secret = AsyncMock()
    p1, p2 = _patched(svc)
    with p1, p2:
        result = await manage._set_secret_internal("k", "v", None, force=True)
    assert result.ok
    assert result.data["action"] == "created"
    svc.get_secret.assert_not_called()
    svc.set_secret.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_missing_secret_is_not_ok() -> None:
    svc = MagicMock()
    svc.delete_secret = AsyncMock(side_effect=SecretNotFoundError("gone"))
    p1, p2 = _patched(svc)
    with p1, p2:
        result = await manage._delete_internal("gone")
    assert not result.ok


def test_registered_on_core_admin() -> None:
    from cli.resources.secrets import app

    names = {c.name for c in app.registered_commands}
    assert names == {"set", "get", "list", "delete"}
