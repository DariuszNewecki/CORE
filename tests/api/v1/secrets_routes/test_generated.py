from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.v1.secrets_routes import rotate_secret


# ID: f1aae443-f89c-47a7-8cfd-ac8753b9882d
async def test_rotate_secret():
    """Test happy path of rotate_secret: returns dict and calls service."""
    mock_svc = MagicMock()
    mock_svc.rotate_secret = AsyncMock()
    mock_session = MagicMock()
    body = MagicMock()
    body.new_value = "new-secret-value"

    result = await rotate_secret(
        key="my_key", body=body, session=mock_session, svc=mock_svc
    )

    mock_svc.rotate_secret.assert_awaited_once_with(
        mock_session, "my_key", "new-secret-value"
    )
    assert result == {"key": "my_key", "rotated": True}


from unittest.mock import patch

from api.v1.secrets_routes import delete_secret


# ID: 1cce6761-4a87-4b70-b6b0-d58380d57430
async def test_delete_secret():
    mock_session = MagicMock()
    mock_svc = AsyncMock()

    with (
        patch("api.v1.secrets_routes.get_api_session", return_value=mock_session),
        patch("api.v1.secrets_routes.get_secrets_service_dep", return_value=mock_svc),
    ):
        result = await delete_secret("my_key", session=mock_session, svc=mock_svc)

    mock_svc.delete_secret.assert_awaited_once_with(mock_session, "my_key")
    assert result == {"key": "my_key", "deleted": True}


from api.v1.secrets_routes import get_secret


# ID: daa542c1-e028-43bd-902a-e1531918fe6a
async def test_get_secret():
    mock_session = MagicMock()
    mock_svc = AsyncMock()
    mock_svc.get_secret = AsyncMock(return_value="my_secret_value")

    with patch("api.v1.secrets_routes.get_secret", return_value=None):
        # Test happy path without show
        result = await get_secret("test_key", session=mock_session, svc=mock_svc)

    mock_svc.get_secret.assert_awaited_once_with(
        mock_session, "test_key", audit_context="api:get"
    )
    assert result == {"key": "test_key", "exists": True}

    # Test happy path with show
    with patch("api.v1.secrets_routes.get_secret", return_value=None):
        result_with_show = await get_secret(
            "test_key", show=True, session=mock_session, svc=mock_svc
        )

    mock_svc.get_secret.assert_awaited_with(
        mock_session, "test_key", audit_context="api:get"
    )
    assert result_with_show == {
        "key": "test_key",
        "exists": True,
        "value": "my_secret_value",
    }


import pytest

from api.v1.secrets_routes import list_secrets


@pytest.mark.asyncio
# ID: 431484d5-348b-4a39-9eab-4ed12f07613e
async def test_list_secrets():
    mock_session = AsyncMock()
    mock_svc = MagicMock()
    mock_svc.list_secrets = AsyncMock(
        return_value=[
            {"key": "secret1", "created_at": "2024-01-01"},
            {"key": "secret2", "created_at": "2024-02-01"},
        ]
    )

    result = await list_secrets(session=mock_session, svc=mock_svc)

    assert result == {
        "secrets": [
            {"key": "secret1", "created_at": "2024-01-01"},
            {"key": "secret2", "created_at": "2024-02-01"},
        ],
        "count": 2,
    }
    mock_svc.list_secrets.assert_awaited_once_with(mock_session)
