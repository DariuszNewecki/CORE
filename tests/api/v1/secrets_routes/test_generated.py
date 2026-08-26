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
