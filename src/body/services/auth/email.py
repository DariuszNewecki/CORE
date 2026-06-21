# src/body/services/auth/email.py
"""Transactional email delivery via Resend (ADR-124).

Graceful degradation: if RESEND_API_KEY is unset the send is skipped and
the caller receives the raw token to surface in the API response (dev mode).
Routes check ``email_sent`` in the returned dict to decide whether to include
the token in the response.

All sends are fire-and-forget — network failures are logged, not raised, so
auth operations never fail because email is down.
"""

from __future__ import annotations

import httpx

from shared.logger import getLogger


logger = getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


# ID: b4e2f9c1-3a7d-4e8b-a0c6-5d1f3a9e2b7c
async def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    api_key: str,
    from_address: str = "CORE <noreply@core-governance.com>",
) -> bool:
    """Send one email via Resend.  Returns True on success."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "from": from_address,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
        if resp.status_code not in (200, 201):
            logger.warning("Resend delivery failed: %s %s", resp.status_code, resp.text)
            return False
        return True
    except Exception as exc:
        logger.warning("Email send error to %s: %s", to, exc)
        return False


# ID: 7c3a1f9e-2d4b-4e8c-b5f0-1a6d3c7f2e9b
async def send_verification_email(
    *, to: str, token: str, base_url: str, api_key: str, from_address: str
) -> bool:
    link = f"{base_url.rstrip('/')}/verify-email?token={token}"
    html = (
        "<p>Welcome to CORE. Please verify your email address by clicking the link below.</p>"
        f'<p><a href="{link}">Verify my email</a></p>'
        f"<p>Or copy this link: {link}</p>"
        "<p>This link expires in 24 hours.</p>"
    )
    return await send_email(
        to=to,
        subject="Verify your CORE account",
        html=html,
        api_key=api_key,
        from_address=from_address,
    )


# ID: 4f8d2a7c-1e3b-4c9e-b6a0-3d5c1a8f4e2b
async def send_password_reset_email(
    *, to: str, token: str, base_url: str, api_key: str, from_address: str
) -> bool:
    link = f"{base_url.rstrip('/')}/reset-password?token={token}"
    html = (
        "<p>A password reset was requested for your CORE account.</p>"
        f'<p><a href="{link}">Reset my password</a></p>'
        f"<p>Or copy this link: {link}</p>"
        "<p>This link expires in 1 hour. If you did not request this, ignore this email.</p>"
    )
    return await send_email(
        to=to,
        subject="Reset your CORE password",
        html=html,
        api_key=api_key,
        from_address=from_address,
    )


# ID: 2e9b5c3f-4a1d-4f8e-b7c0-6a2d1c5e3f9b
async def send_invitation_email(
    *,
    to: str,
    token: str,
    role: str,
    org_name: str,
    base_url: str,
    api_key: str,
    from_address: str,
) -> bool:
    link = f"{base_url.rstrip('/')}/register?token={token}"
    html = (
        f"<p>You have been invited to join <strong>{org_name}</strong> on CORE"
        f" as <strong>{role}</strong>.</p>"
        f'<p><a href="{link}">Accept invitation</a></p>'
        f"<p>Or copy this link: {link}</p>"
        "<p>This invitation expires in 7 days.</p>"
    )
    return await send_email(
        to=to,
        subject=f"You're invited to join {org_name} on CORE",
        html=html,
        api_key=api_key,
        from_address=from_address,
    )
