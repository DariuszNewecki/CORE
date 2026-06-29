# tests/will/governance/test_auth_runner.py

"""Unit tests for AuthRunner — the Will-layer auth facade (#718)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.governance.auth_runner import AuthLockedError, AuthRunner


def _make_runner(resend_api_key: str | None = None) -> AuthRunner:
    session = MagicMock()
    return AuthRunner(
        session=session,
        jwt_secret="test-secret",
        access_expire_minutes=60,
        refresh_expire_days=30,
        resend_api_key=resend_api_key,
        app_base_url="http://localhost:8000",
        mail_from="test@example.com",
    )


# ID: c6d7e8f9-0a1b-4c2d-3e4f-5a6b7c8d9e0f
def test_auth_locked_error_is_re_exported() -> None:
    from body.services.auth.service import AuthLockedError as _BodyError

    assert AuthLockedError is _BodyError


# ID: d7e8f9a0-1b2c-4d3e-5f6a-7b8c9d0e1f2a
async def test_register_delegates_to_auth_service() -> None:
    runner = _make_runner()
    with patch.object(runner._svc, "register", new_callable=AsyncMock) as mock:
        mock.return_value = {"user_id": "u1", "email_verify_token": "tok"}
        result = await runner.register("a@b.com", "pw")
    mock.assert_awaited_once()
    assert result["user_id"] == "u1"


# ID: e8f9a0b1-2c3d-4e5f-6a7b-8c9d0e1f2a3b
async def test_send_verification_email_skipped_without_api_key() -> None:
    runner = _make_runner(resend_api_key=None)
    result = await runner.send_verification_email("a@b.com", "tok")
    assert result is False


# ID: f9a0b1c2-3d4e-5f6a-7b8c-9d0e1f2a3b4c
async def test_send_verification_email_calls_body_when_key_present() -> None:
    runner = _make_runner(resend_api_key="key-abc")
    with patch(
        "will.governance.auth_runner._send_verification_email", new_callable=AsyncMock
    ) as mock:
        mock.return_value = True
        result = await runner.send_verification_email("a@b.com", "tok")
    assert result is True
    mock.assert_awaited_once_with(
        to="a@b.com",
        token="tok",
        base_url="http://localhost:8000",
        api_key="key-abc",
        from_address="test@example.com",
    )


# ID: a0b1c2d3-4e5f-6a7b-8c9d-0e1f2a3b4c5d
async def test_send_password_reset_email_skipped_without_api_key() -> None:
    runner = _make_runner(resend_api_key=None)
    result = await runner.send_password_reset_email("a@b.com", "tok")
    assert result is False


# ID: b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e
async def test_send_invitation_email_skipped_without_api_key() -> None:
    runner = _make_runner(resend_api_key=None)
    result = await runner.send_invitation_email("a@b.com", "tok", "analyst", "OrgX")
    assert result is False
