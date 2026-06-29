# src/will/governance/auth_runner.py

"""Auth runner facade — Will-layer entry point for the /auth API (ADR-124, #718).

Wraps ``AuthService`` (Body) and the Resend email helpers so the API layer has
a single, architecture-compliant import point in Will.  All session and
configuration values are injected by the API's DI factory; no Settings import
here.

Re-exports ``AuthLockedError`` so ``auth_routes`` can catch it without a direct
Body import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from body.services.auth.email import (
    send_invitation_email as _send_invitation_email,
)
from body.services.auth.email import (
    send_password_reset_email as _send_password_reset_email,
)
from body.services.auth.email import (
    send_verification_email as _send_verification_email,
)
from body.services.auth.service import AuthLockedError, AuthService
from shared.logger import getLogger


__all__ = ["AuthLockedError", "AuthRunner"]

logger = getLogger(__name__)


# ID: 62c60818-d34d-4e81-9304-7fa14be22ca3
class AuthRunner:
    """Will-layer facade over AuthService and transactional email helpers.

    One instance per request, constructed by the API DI factory.
    """

    def __init__(
        self,
        session: AsyncSession,
        jwt_secret: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
        resend_api_key: str | None = None,
        app_base_url: str = "",
        mail_from: str = "",
    ) -> None:
        self._svc = AuthService(
            session=session,
            jwt_secret=jwt_secret,
            access_expire_minutes=access_expire_minutes,
            refresh_expire_days=refresh_expire_days,
        )
        self._resend_api_key = resend_api_key
        self._app_base_url = app_base_url
        self._mail_from = mail_from

    # ------------------------------------------------------------------
    # AuthService delegation
    # ------------------------------------------------------------------

    # ID: eccdb6a0-3fec-48ec-9e25-20e2f654254e
    async def register(
        self,
        email: str,
        password: str,
        org_name: str | None = None,
        invitation_token: str | None = None,
    ) -> dict[str, Any]:
        return await self._svc.register(
            email=email,
            password=password,
            org_name=org_name,
            invitation_token=invitation_token,
        )

    # ID: f8446d8e-ccef-4022-af95-8798c9b541d9
    async def verify_email(self, token: str) -> str:
        return await self._svc.verify_email(token)

    # ID: 25b04363-365e-4878-aa74-6636cd2684ff
    async def login(
        self, email: str, password: str, ip: str | None, ua: str | None
    ) -> dict[str, str] | None:
        return await self._svc.login(email, password, ip=ip, ua=ua)

    # ID: 115a13cc-9a88-4fdb-898d-4194ce98520a
    async def refresh(self, raw_refresh_token: str) -> dict[str, str] | None:
        return await self._svc.refresh(raw_refresh_token)

    # ID: deef1019-efe1-4d6e-8136-a414679a97ad
    async def logout(self, raw_refresh_token: str) -> None:
        await self._svc.logout(raw_refresh_token)

    # ID: 07a2161e-900c-42d2-8698-64f91859d087
    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> bool:
        return await self._svc.change_password(
            user_id=user_id,
            current_password=current_password,
            new_password=new_password,
        )

    # ID: fb42e2a2-8970-4f4c-8543-021efae5ddc1
    async def request_password_reset(self, email: str) -> str | None:
        return await self._svc.request_password_reset(email)

    # ID: 3351508e-2f3a-45ce-8bf7-85a7582b229f
    async def reset_password(self, raw_token: str, new_password: str) -> bool:
        return await self._svc.reset_password(raw_token, new_password)

    # ID: 6c387bba-7160-4129-9744-1474cd534a3e
    async def create_invitation(
        self,
        *,
        email: str,
        org_id: str | None,
        role: str,
        created_by_id: str,
    ) -> str:
        return await self._svc.create_invitation(
            email=email,
            org_id=org_id,
            role=role,
            created_by_id=created_by_id,
        )

    # ID: 2b570763-a52b-4e9e-87eb-19c3be753eed
    async def promote_user(
        self,
        user_id: str,
        org_id: str | None,
        role: str,
        promoted_by_id: str,
        promoter_role: str,
    ) -> None:
        await self._svc.promote_user(
            user_id=user_id,
            org_id=org_id,
            role=role,
            promoted_by_id=promoted_by_id,
            promoter_role=promoter_role,
        )

    # ID: 042fcd2b-e0f5-4449-ae18-57ee8a7abffd
    async def set_active(self, user_id: str, active: bool, actor_id: str) -> None:
        await self._svc.set_active(user_id=user_id, active=active, actor_id=actor_id)

    # ID: 1808a500-67eb-4d89-90fc-e56a1a2d9e53
    async def create_api_key(
        self,
        org_id: str,
        created_by_id: str,
        label: str,
        role: str,
        expires_at: str | None,
    ) -> dict[str, Any]:
        return await self._svc.create_api_key(
            org_id=org_id,
            created_by_id=created_by_id,
            label=label,
            role=role,
            expires_at=expires_at,
        )

    # ID: 076b8b4d-131d-4acf-b15a-2ea2185a7b7f
    async def revoke_api_key(self, *, key_id: str, org_id: str, actor_id: str) -> bool:
        return await self._svc.revoke_api_key(
            key_id=key_id, org_id=org_id, actor_id=actor_id
        )

    # ID: 1f65b5ec-aeaf-4c7e-b14c-b60ab4d63670
    async def list_api_keys(self, *, org_id: str) -> list[dict[str, Any]]:
        return await self._svc.list_api_keys(org_id=org_id)

    # ------------------------------------------------------------------
    # Email helpers — no-op when RESEND_API_KEY is not configured
    # ------------------------------------------------------------------

    # ID: c3ce3b4c-5fa7-411e-889c-f867b430b4c1
    async def send_verification_email(self, to: str, token: str) -> bool:
        """Send account-verification email. Returns False when email is not configured."""
        if not self._resend_api_key:
            return False
        return await _send_verification_email(
            to=to,
            token=token,
            base_url=self._app_base_url,
            api_key=self._resend_api_key,
            from_address=self._mail_from,
        )

    # ID: c3419a3a-09e8-4d8f-a707-709b5f452706
    async def send_password_reset_email(self, to: str, token: str) -> bool:
        """Send password-reset email. Returns False when email is not configured."""
        if not self._resend_api_key:
            return False
        return await _send_password_reset_email(
            to=to,
            token=token,
            base_url=self._app_base_url,
            api_key=self._resend_api_key,
            from_address=self._mail_from,
        )

    # ID: 7c098bca-f56c-4ef6-a1c6-80ed54e02dc3
    async def send_invitation_email(
        self, to: str, token: str, role: str, org_name: str
    ) -> bool:
        """Send invitation email. Returns False when email is not configured."""
        if not self._resend_api_key:
            return False
        return await _send_invitation_email(
            to=to,
            token=token,
            role=role,
            org_name=org_name,
            base_url=self._app_base_url,
            api_key=self._resend_api_key,
            from_address=self._mail_from,
        )
