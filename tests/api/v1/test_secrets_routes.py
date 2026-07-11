# tests/api/v1/test_secrets_routes.py

"""Tests for secrets routes — mock the SecretsService dependency."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.v1.secrets_routes import (
    delete_secret,
    get_secret,
    list_secrets,
    rotate_secret,
    set_secret,
)
from shared.exceptions import SecretNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session() -> MagicMock:
    return MagicMock()


def _mock_svc(**method_returns: object) -> MagicMock:
    svc = MagicMock()
    for method, return_value in method_returns.items():
        setattr(svc, method, AsyncMock(return_value=return_value))
    return svc


def _mock_svc_raising(method: str, exc: Exception) -> MagicMock:
    svc = MagicMock()
    setattr(svc, method, AsyncMock(side_effect=exc))
    return svc


# ---------------------------------------------------------------------------
# list_secrets
# ---------------------------------------------------------------------------


async def test_list_secrets_empty():
    svc = _mock_svc(list_secrets=[])
    result = await list_secrets(session=_mock_session(), svc=svc)
    assert result == {"secrets": [], "count": 0}


async def test_list_secrets_returns_keys():
    data = [{"key": "k1", "last_rotated_at": None, "created_at": "2026-01-01"}]
    svc = _mock_svc(list_secrets=data)
    result = await list_secrets(session=_mock_session(), svc=svc)
    assert result["count"] == 1
    assert result["secrets"][0]["key"] == "k1"


# ---------------------------------------------------------------------------
# set_secret
# ---------------------------------------------------------------------------


async def test_set_secret_creates_new():
    svc = MagicMock()
    svc.get_secret = AsyncMock(side_effect=SecretNotFoundError("new_key"))
    svc.set_secret = AsyncMock(return_value=None)

    from api.v1.secrets_routes import SecretSetRequest

    body = SecretSetRequest(key="new_key", value="s3cr3t", description=None, force=False)
    result = await set_secret(body=body, session=_mock_session(), svc=svc)
    assert result == {"key": "new_key", "action": "created"}
    svc.set_secret.assert_awaited_once()


async def test_set_secret_conflict_without_force():
    svc = MagicMock()
    svc.get_secret = AsyncMock(return_value="existing_value")

    from fastapi import HTTPException

    from api.v1.secrets_routes import SecretSetRequest

    body = SecretSetRequest(key="existing", value="new", force=False)
    with pytest.raises(HTTPException) as exc_info:
        await set_secret(body=body, session=_mock_session(), svc=svc)
    assert exc_info.value.status_code == 409


async def test_set_secret_overwrites_with_force():
    svc = MagicMock()
    svc.get_secret = AsyncMock(return_value="old_value")
    svc.set_secret = AsyncMock(return_value=None)

    from api.v1.secrets_routes import SecretSetRequest

    body = SecretSetRequest(key="existing", value="new", force=True)
    result = await set_secret(body=body, session=_mock_session(), svc=svc)
    assert result == {"key": "existing", "action": "overwritten"}


# ---------------------------------------------------------------------------
# get_secret
# ---------------------------------------------------------------------------


async def test_get_secret_exists_no_show():
    svc = _mock_svc(get_secret="plaintext_value")
    result = await get_secret(key="mykey", show=False, session=_mock_session(), svc=svc)
    assert result["exists"] is True
    assert "value" not in result


async def test_get_secret_show_returns_value():
    svc = _mock_svc(get_secret="plaintext_value")
    result = await get_secret(key="mykey", show=True, session=_mock_session(), svc=svc)
    assert result["value"] == "plaintext_value"


async def test_get_secret_not_found():
    svc = _mock_svc_raising("get_secret", SecretNotFoundError("missing"))

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_secret(key="missing", show=False, session=_mock_session(), svc=svc)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# delete_secret
# ---------------------------------------------------------------------------


async def test_delete_secret_ok():
    svc = _mock_svc(delete_secret=None)
    result = await delete_secret(key="k", session=_mock_session(), svc=svc)
    assert result == {"key": "k", "deleted": True}


async def test_delete_secret_not_found():
    svc = _mock_svc_raising("delete_secret", SecretNotFoundError("k"))

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await delete_secret(key="k", session=_mock_session(), svc=svc)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# rotate_secret
# ---------------------------------------------------------------------------


async def test_rotate_secret_ok():
    svc = _mock_svc(rotate_secret=None)

    from api.v1.secrets_routes import SecretRotateRequest

    body = SecretRotateRequest(new_value="new_val")
    result = await rotate_secret(key="k", body=body, session=_mock_session(), svc=svc)
    assert result == {"key": "k", "rotated": True}


async def test_rotate_secret_not_found():
    svc = _mock_svc_raising("rotate_secret", SecretNotFoundError("k"))

    from fastapi import HTTPException

    from api.v1.secrets_routes import SecretRotateRequest

    body = SecretRotateRequest(new_value="v")
    with pytest.raises(HTTPException) as exc_info:
        await rotate_secret(key="k", body=body, session=_mock_session(), svc=svc)
    assert exc_info.value.status_code == 404
