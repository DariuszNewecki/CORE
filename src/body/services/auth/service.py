# src/body/services/auth/service.py
"""Auth business logic — register, login, verify, reset, promote (ADR-124).

Receives all configuration (JWT secret, token expiry) via constructor so that
the Body layer never imports Settings directly (architecture.boundary.settings_access).

All DB access is raw SQL via SQLAlchemy ``text()`` — consistent with the
rest of the codebase.  Session is injected per-request from the API layer.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.auth.deny_list import deny_list
from body.services.auth.password import hash_password, verify_password
from body.services.auth.tokens import (
    create_access_token,
    create_email_verify_token,
    decode_email_verify_token,
    generate_opaque_token,
    hash_token,
)
from shared.logger import getLogger


logger = getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_LOCKOUT_THRESHOLD = 10
_LOCKOUT_WINDOW_MINUTES = 15
_LOCKOUT_DURATION_MINUTES = 15


# ID: b2f4e7c1-3a8d-4f9e-b5c0-6d1a3f7e2c9b
class AuthLockedError(Exception):
    """Raised when a login attempt is made on a temporarily locked account."""

    def __init__(self, locked_until: datetime) -> None:
        self.locked_until = locked_until
        super().__init__(f"Account locked until {locked_until.isoformat()}")


_SLUG_RE = re.compile(r"[^a-z0-9]+")


# ID: 6b1d4e8a-2f3c-4a7e-9d0b-5c1f6a3e8b2d
def _slugify(name: str) -> str:
    """Produce a URL-safe slug from an org name."""
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return _SLUG_RE.sub("-", normalized.lower()).strip("-")[:60]


# ID: 3a7f9d2e-1b4c-4e6a-8f0d-2c5a1e7b3f9d
class AuthService:
    """Stateless auth operations.  One instance per request (constructed in DI)."""

    def __init__(
        self,
        session: AsyncSession,
        jwt_secret: str,
        access_expire_minutes: int = 60,
        refresh_expire_days: int = 30,
    ) -> None:
        self._session = session
        self._jwt_secret = jwt_secret
        self._access_expire_minutes = access_expire_minutes
        self._refresh_expire_days = refresh_expire_days

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    # ID: 8e2c5b1a-4f7d-4a3e-9b0c-6d1f3a8e5b2c
    async def register(
        self,
        email: str,
        password: str,
        org_name: str | None = None,
        invitation_token: str | None = None,
    ) -> dict[str, Any]:
        """Register a new user.

        Returns a dict with user_id and email_verify_token.
        Raises ValueError on validation failures.
        """
        email = email.strip().lower()
        if not _EMAIL_RE.match(email):
            raise ValueError("Invalid email address.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")

        existing = await self._session.execute(
            text("SELECT id FROM core.users WHERE email = :email"), {"email": email}
        )
        if existing.fetchone():
            raise ValueError("An account with this email already exists.")

        pw_hash = hash_password(password)
        result = await self._session.execute(
            text(
                "INSERT INTO core.users (email, password_hash, auth_method, email_verified)"
                " VALUES (:email, :pw_hash, 'email', false)"
                " RETURNING id"
            ),
            {"email": email, "pw_hash": pw_hash},
        )
        user_id: UUID = result.scalar_one()

        invite_org_id: UUID | None = None
        invite_role: str | None = None

        if invitation_token:
            invite_org_id, _invite_role = await self._consume_invitation(
                user_id, invitation_token
            )

        if not invite_org_id and org_name:
            await self._handle_org_on_register(user_id, org_name.strip())

        if not invite_org_id:
            await self._session.execute(
                text(
                    "INSERT INTO core.org_memberships (user_id, organisation_id, role)"
                    " VALUES (:uid, NULL, 'visitor')"
                ),
                {"uid": user_id},
            )

        verify_token = create_email_verify_token(str(user_id), self._jwt_secret)

        await self._log_event("registered", user_id=user_id)
        await self._session.commit()

        logger.info("User registered: %s", email)
        return {"user_id": str(user_id), "email_verify_token": verify_token}

    # ID: 2f4c8e1a-6b3d-4a9e-b0f7-1d5c2a6e4f8b
    async def _handle_org_on_register(self, user_id: UUID, org_name: str) -> None:
        slug_base = _slugify(org_name)
        existing = await self._session.execute(
            text("SELECT id FROM core.organisations WHERE lower(name) = lower(:name)"),
            {"name": org_name},
        )
        row = existing.fetchone()
        if row:
            org_id: UUID = row[0]
            await self._session.execute(
                text(
                    "INSERT INTO core.org_memberships (user_id, organisation_id, role)"
                    " VALUES (:uid, :oid, 'visitor')"
                ),
                {"uid": user_id, "oid": org_id},
            )
        else:
            slug = slug_base
            suffix = 1
            while True:
                clash = await self._session.execute(
                    text("SELECT id FROM core.organisations WHERE slug = :slug"),
                    {"slug": slug},
                )
                if not clash.fetchone():
                    break
                slug = f"{slug_base}-{suffix}"
                suffix += 1

            org_result = await self._session.execute(
                text(
                    "INSERT INTO core.organisations (name, slug, created_by)"
                    " VALUES (:name, :slug, :uid)"
                    " RETURNING id"
                ),
                {"name": org_name, "slug": slug, "uid": user_id},
            )
            org_id = org_result.scalar_one()
            await self._session.execute(
                text(
                    "INSERT INTO core.org_memberships (user_id, organisation_id, role)"
                    " VALUES (:uid, :oid, 'org_admin')"
                ),
                {"uid": user_id, "oid": org_id},
            )

    # ID: 9d5a2f7c-3e1b-4c8a-b0d6-4f2c1a5e9b7d
    async def _consume_invitation(
        self, user_id: UUID, raw_token: str
    ) -> tuple[UUID | None, str | None]:
        token_hash = hash_token(raw_token)
        row = await self._session.execute(
            text(
                "SELECT id, organisation_id, role FROM core.invitations"
                " WHERE token_hash = :hash AND accepted_at IS NULL"
                " AND expires_at > now()"
            ),
            {"hash": token_hash},
        )
        inv = row.fetchone()
        if not inv:
            raise ValueError("Invitation link is invalid or has expired.")

        inv_id, org_id, role = inv
        await self._session.execute(
            text("UPDATE core.invitations SET accepted_at = now() WHERE id = :id"),
            {"id": inv_id},
        )
        await self._session.execute(
            text(
                "INSERT INTO core.org_memberships"
                " (user_id, organisation_id, role, promoted_at)"
                " VALUES (:uid, :oid, :role, now())"
                " ON CONFLICT (user_id, organisation_id) DO UPDATE SET role = EXCLUDED.role"
            ),
            {"uid": user_id, "oid": org_id, "role": role},
        )
        await self._session.execute(
            text("UPDATE core.users SET email_verified = true WHERE id = :uid"),
            {"uid": user_id},
        )
        return org_id, role

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------

    # ID: 1c3e7a9f-5b2d-4f8c-a0e6-3d1b5c7a2f9e
    async def verify_email(self, token: str) -> str:
        """Verify email via JWT token.  Returns user_id on success."""
        try:
            user_id = decode_email_verify_token(token, self._jwt_secret)
        except Exception as exc:
            raise ValueError("Invalid or expired verification link.") from exc

        await self._session.execute(
            text(
                "UPDATE core.users SET email_verified = true"
                " WHERE id = :uid AND email_verified = false"
            ),
            {"uid": user_id},
        )
        await self._log_event("email_verified", user_id=UUID(user_id))
        await self._session.commit()
        return user_id

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------

    # ID: 4f2a8d1e-7c3b-4e9a-b5f0-2d6c1a4e7f3b
    async def login(
        self, email: str, password: str, ip: str | None, ua: str | None
    ) -> dict[str, str] | None:
        """Verify credentials and issue tokens.

        Returns dict with access_token and refresh_token, or None on failure.
        Raises AuthLockedError if the account is temporarily locked.
        """
        email = email.strip().lower()
        row = await self._session.execute(
            text(
                "SELECT id, password_hash, email_verified, is_active, locked_until"
                " FROM core.users WHERE email = :email"
            ),
            {"email": email},
        )
        user = row.fetchone()
        if not user:
            await self._log_event(
                "login_failed",
                metadata={"email": email, "reason": "unknown_email"},
                ip=ip,
                ua=ua,
            )
            return None

        user_id, pw_hash, email_verified, is_active, locked_until = user

        if locked_until and locked_until > datetime.now(UTC):
            raise AuthLockedError(locked_until)

        if not is_active:
            await self._log_event(
                "login_failed",
                user_id=user_id,
                metadata={"reason": "suspended"},
                ip=ip,
                ua=ua,
            )
            return None

        if pw_hash is None or not verify_password(password, pw_hash):
            await self._log_event(
                "login_failed",
                user_id=user_id,
                metadata={"reason": "bad_password"},
                ip=ip,
                ua=ua,
            )
            await self._maybe_lock_account(user_id)
            await self._session.commit()
            return None

        if not email_verified:
            await self._log_event(
                "login_failed",
                user_id=user_id,
                metadata={"reason": "email_not_verified"},
                ip=ip,
                ua=ua,
            )
            return None

        membership = await self._get_membership(user_id)
        role = membership["role"] if membership else "visitor"
        org_id = (
            str(membership["org_id"]) if membership and membership["org_id"] else None
        )

        access_token = create_access_token(
            str(user_id),
            email,
            role,
            org_id,
            self._jwt_secret,
            self._access_expire_minutes,
        )
        raw_refresh, hashed_refresh = generate_opaque_token()
        family_id = uuid4()
        expires_at = datetime.now(UTC) + timedelta(days=self._refresh_expire_days)

        await self._session.execute(
            text(
                "INSERT INTO core.refresh_tokens"
                " (user_id, token_hash, family_id, expires_at)"
                " VALUES (:uid, :hash, :fid, :exp)"
            ),
            {
                "uid": user_id,
                "hash": hashed_refresh,
                "fid": family_id,
                "exp": expires_at,
            },
        )
        await self._session.execute(
            text(
                "UPDATE core.users SET last_login_at = now(), locked_until = NULL"
                " WHERE id = :uid"
            ),
            {"uid": user_id},
        )
        await self._log_event("login", user_id=user_id, ip=ip, ua=ua)
        await self._session.commit()

        return {"access_token": access_token, "refresh_token": raw_refresh}

    # ID: 6d1f3a7c-2e4b-4c8a-b9f0-5a2d1c6e3f7b
    async def logout(self, raw_refresh_token: str) -> None:
        """Revoke a refresh token on logout."""
        token_hash = hash_token(raw_refresh_token)
        result = await self._session.execute(
            text(
                "UPDATE core.refresh_tokens SET revoked = true"
                " WHERE token_hash = :hash AND revoked = false"
                " RETURNING user_id"
            ),
            {"hash": token_hash},
        )
        row = result.fetchone()
        if row:
            await self._log_event("logout", user_id=row[0])
        await self._session.commit()

    # ------------------------------------------------------------------
    # Token refresh
    # ------------------------------------------------------------------

    # ID: 5b2e9c4a-1f7d-4a3e-8c0b-6d2f1a5e9c3b
    async def refresh(self, raw_refresh_token: str) -> dict[str, str] | None:
        """Exchange a valid refresh token for a new access JWT + rotated refresh token.

        Implements token family rotation (ADR-124 D4):
        - Marks the consumed token as used.
        - Inserts a new token in the same family.
        - Reuse of an already-used token revokes the entire family (theft signal).
        Returns None on any validation failure.
        """
        token_hash = hash_token(raw_refresh_token)
        row = await self._session.execute(
            text(
                "SELECT rt.id, rt.user_id, rt.family_id, rt.used_at,"
                "       u.email, u.is_active"
                " FROM core.refresh_tokens rt"
                " JOIN core.users u ON u.id = rt.user_id"
                " WHERE rt.token_hash = :hash"
                " AND rt.revoked = false AND rt.expires_at > now()"
            ),
            {"hash": token_hash},
        )
        rec = row.fetchone()
        if not rec:
            return None

        token_id, user_id, family_id, used_at, email, is_active = rec

        if used_at is not None:
            await self._session.execute(
                text(
                    "UPDATE core.refresh_tokens SET revoked = true"
                    " WHERE family_id = :fid"
                ),
                {"fid": family_id},
            )
            await self._log_event(
                "token_refresh_rejected",
                user_id=user_id,
                metadata={"reason": "reuse_detected", "family_id": str(family_id)},
            )
            await self._session.commit()
            return None

        if not is_active:
            return None

        await self._session.execute(
            text("UPDATE core.refresh_tokens SET used_at = now() WHERE id = :tid"),
            {"tid": token_id},
        )

        raw_new, hashed_new = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(days=self._refresh_expire_days)
        await self._session.execute(
            text(
                "INSERT INTO core.refresh_tokens"
                " (user_id, token_hash, family_id, expires_at)"
                " VALUES (:uid, :hash, :fid, :exp)"
            ),
            {"uid": user_id, "hash": hashed_new, "fid": family_id, "exp": expires_at},
        )

        membership = await self._get_membership(user_id)
        role = membership["role"] if membership else "visitor"
        org_id = (
            str(membership["org_id"]) if membership and membership["org_id"] else None
        )

        await self._log_event("token_refreshed", user_id=user_id)
        await self._session.commit()

        return {
            "access_token": create_access_token(
                str(user_id),
                email,
                role,
                org_id,
                self._jwt_secret,
                self._access_expire_minutes,
            ),
            "refresh_token": raw_new,
        }

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    # ID: 7a4c1f9e-3d2b-4e7a-b0c8-5f1a3d7c2e9f
    async def request_password_reset(self, email: str) -> str | None:
        """Generate a reset token.  Returns raw token or None if email unknown.

        Callers must send this token to the user's email — this service does
        not send email (no I/O beyond DB).
        """
        email = email.strip().lower()
        row = await self._session.execute(
            text("SELECT id FROM core.users WHERE email = :email AND is_active = true"),
            {"email": email},
        )
        user = row.fetchone()
        if not user:
            return None

        user_id = user[0]
        await self._session.execute(
            text(
                "UPDATE core.password_reset_tokens SET used = true"
                " WHERE user_id = :uid AND used = false"
            ),
            {"uid": user_id},
        )

        raw, hashed = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        await self._session.execute(
            text(
                "INSERT INTO core.password_reset_tokens (user_id, token_hash, expires_at)"
                " VALUES (:uid, :hash, :exp)"
            ),
            {"uid": user_id, "hash": hashed, "exp": expires_at},
        )
        await self._log_event("password_reset_requested", user_id=user_id)
        await self._session.commit()
        return raw

    # ID: 2e7b5d1c-4a3f-4c9e-b8a0-1f6d3c5a7e2b
    async def reset_password(self, raw_token: str, new_password: str) -> bool:
        """Apply a password reset.  Returns True on success."""
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters.")

        token_hash = hash_token(raw_token)
        row = await self._session.execute(
            text(
                "SELECT id, user_id FROM core.password_reset_tokens"
                " WHERE token_hash = :hash AND used = false AND expires_at > now()"
            ),
            {"hash": token_hash},
        )
        rec = row.fetchone()
        if not rec:
            return False

        token_id, user_id = rec
        pw_hash = hash_password(new_password)

        await self._session.execute(
            text("UPDATE core.users SET password_hash = :pw WHERE id = :uid"),
            {"pw": pw_hash, "uid": user_id},
        )
        await self._session.execute(
            text("UPDATE core.password_reset_tokens SET used = true WHERE id = :id"),
            {"id": token_id},
        )
        await self._session.execute(
            text("UPDATE core.refresh_tokens SET revoked = true WHERE user_id = :uid"),
            {"uid": user_id},
        )
        await self._log_event("password_reset_completed", user_id=user_id)
        await self._session.commit()
        return True

    # ------------------------------------------------------------------
    # Role promotion
    # ------------------------------------------------------------------

    # ID: 9f3d6a2e-5c1b-4e8a-b7f0-3a1d5c9e2f6b
    async def promote_user(
        self,
        user_id: str,
        org_id: str | None,
        role: str,
        promoted_by_id: str,
        promoter_role: str,
    ) -> None:
        """Change a user's role within an org.

        ORG_ADMIN may promote up to AUDITOR within their own org.
        PLATFORM_ADMIN may promote to any role.
        Raises ValueError on permission failure.
        """
        _ORG_ADMIN_MAX = {"visitor", "analyst", "auditor"}
        if promoter_role == "org_admin" and role not in _ORG_ADMIN_MAX:
            raise ValueError("ORG_ADMIN may only promote up to AUDITOR.")
        if promoter_role not in {"org_admin", "platform_admin"}:
            raise ValueError("Insufficient permissions to promote users.")

        await self._session.execute(
            text(
                "INSERT INTO core.org_memberships"
                " (user_id, organisation_id, role, promoted_by, promoted_at)"
                " VALUES (:uid, :oid, :role, :by, now())"
                " ON CONFLICT (user_id, organisation_id) DO UPDATE"
                " SET role = EXCLUDED.role, promoted_by = EXCLUDED.promoted_by,"
                "     promoted_at = EXCLUDED.promoted_at"
            ),
            {
                "uid": user_id,
                "oid": org_id,
                "role": role,
                "by": promoted_by_id,
            },
        )
        await self._log_event(
            "role_promoted",
            user_id=UUID(user_id),
            actor_id=UUID(promoted_by_id),
            metadata={"role": role, "org_id": org_id},
        )
        await self._session.commit()

    # ------------------------------------------------------------------
    # Account suspension
    # ------------------------------------------------------------------

    # ID: 4c8a1f3e-7d2b-4e6c-b9a0-5f1d3a8e6c2b
    async def set_active(self, user_id: str, active: bool, actor_id: str) -> None:
        """Suspend or reactivate an account (PLATFORM_ADMIN only)."""
        await self._session.execute(
            text("UPDATE core.users SET is_active = :active WHERE id = :uid"),
            {"active": active, "uid": user_id},
        )
        if not active:
            await self._session.execute(
                text(
                    "UPDATE core.refresh_tokens SET revoked = true WHERE user_id = :uid"
                ),
                {"uid": user_id},
            )
            deny_list.add(
                user_id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        else:
            deny_list.remove(user_id)
        event = "account_reactivated" if active else "account_suspended"
        await self._log_event(event, user_id=UUID(user_id), actor_id=UUID(actor_id))
        await self._session.commit()

    # ------------------------------------------------------------------
    # Invitations
    # ------------------------------------------------------------------

    # ID: 6a2e9f4c-1b3d-4c8e-b7a0-5d1f3a6e9b2c
    async def create_invitation(
        self,
        *,
        email: str,
        org_id: str | None,
        role: str,
        created_by_id: str,
    ) -> str:
        """Create an invitation and return the raw token (caller sends the email)."""
        raw, hashed = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(days=7)
        await self._session.execute(
            text(
                "INSERT INTO core.invitations"
                " (email, organisation_id, role, token_hash, created_by, expires_at)"
                " VALUES (:email, :oid, :role, :hash, :by, :exp)"
            ),
            {
                "email": email,
                "oid": org_id,
                "role": role,
                "hash": hashed,
                "by": created_by_id,
                "exp": expires_at,
            },
        )
        await self._log_event(
            "invitation_created",
            actor_id=UUID(created_by_id),
            metadata={"email": email, "role": role, "org_id": org_id},
        )
        await self._session.commit()
        return raw

    # ------------------------------------------------------------------
    # API keys
    # ------------------------------------------------------------------

    # ID: 3c7f1a9e-4d2b-4e6c-b8f0-2a5d1c3e7f9b
    async def create_api_key(
        self,
        *,
        org_id: str,
        created_by_id: str,
        label: str,
        role: str,
        expires_at: str | None = None,
    ) -> dict:
        """Create an API key.  Returns key_id and raw_key (shown once).

        role must be 'analyst' or 'auditor' — enforced by DB CHECK constraint.
        """
        _ALLOWED_KEY_ROLES = {"analyst", "auditor"}
        if role not in _ALLOWED_KEY_ROLES:
            raise ValueError(f"API key role must be one of {_ALLOWED_KEY_ROLES}.")
        raw, hashed = generate_opaque_token()
        result = await self._session.execute(
            text(
                "INSERT INTO core.api_keys"
                " (organisation_id, created_by, key_hash, label, role, expires_at)"
                " VALUES (:oid, :by, :hash, :label, :role, :exp)"
                " RETURNING id"
            ),
            {
                "oid": org_id,
                "by": created_by_id,
                "hash": hashed,
                "label": label,
                "role": role,
                "exp": expires_at,
            },
        )
        key_id = str(result.scalar_one())
        await self._log_event(
            "api_key_created",
            actor_id=UUID(created_by_id),
            metadata={"key_id": key_id, "label": label, "org_id": org_id, "role": role},
        )
        await self._session.commit()
        return {"key_id": key_id, "raw_key": raw}

    # ID: 8f4d2c7a-1e3b-4a9e-b5c0-6d1f4a8e2b7c
    async def revoke_api_key(self, *, key_id: str, org_id: str, actor_id: str) -> bool:
        """Revoke an API key.  Returns False if not found or already revoked."""
        result = await self._session.execute(
            text(
                "UPDATE core.api_keys SET revoked = true"
                " WHERE id = :kid AND organisation_id = :oid AND revoked = false"
                " RETURNING id"
            ),
            {"kid": key_id, "oid": org_id},
        )
        if not result.fetchone():
            return False
        await self._log_event(
            "api_key_revoked",
            actor_id=UUID(actor_id),
            metadata={"key_id": key_id, "org_id": org_id},
        )
        await self._session.commit()
        return True

    # ID: 1d5c3a8f-2e4b-4f7c-b9a0-4c2d1e5a3f8b
    async def list_api_keys(self, *, org_id: str) -> list[dict]:
        """List active (non-revoked) API keys for an organisation."""
        result = await self._session.execute(
            text(
                "SELECT id, label, created_at, last_used_at, expires_at"
                " FROM core.api_keys"
                " WHERE organisation_id = :oid AND revoked = false"
                " ORDER BY created_at DESC"
            ),
            {"oid": org_id},
        )
        return [
            {
                "key_id": str(row[0]),
                "label": row[1],
                "created_at": row[2].isoformat() if row[2] else None,
                "last_used_at": row[3].isoformat() if row[3] else None,
                "expires_at": row[4].isoformat() if row[4] else None,
            }
            for row in result.fetchall()
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # ID: c4e1f8a2-5b3d-4f9c-b7e0-2a6d1c4e8f3b
    async def _maybe_lock_account(self, user_id: object) -> None:
        """Lock the account if the recent failure count crosses the threshold."""
        count_row = await self._session.execute(
            text(
                "SELECT COUNT(*) FROM core.auth_events"
                " WHERE user_id = :uid AND event_type = 'login_failed'"
                " AND created_at > now() - interval '15 minutes'"
            ),
            {"uid": user_id},
        )
        count = count_row.scalar_one()
        if count >= _LOCKOUT_THRESHOLD:
            locked_until = datetime.now(UTC) + timedelta(
                minutes=_LOCKOUT_DURATION_MINUTES
            )
            await self._session.execute(
                text("UPDATE core.users SET locked_until = :lu WHERE id = :uid"),
                {"lu": locked_until, "uid": user_id},
            )
            await self._log_event(
                "account_locked",
                user_id=UUID(str(user_id)),
                metadata={"locked_until": locked_until.isoformat()},
            )

    # ID: 3d9b5e2a-1c4f-4a7e-b8d0-6c2a1f5e3b7d
    async def _get_membership(self, user_id: object) -> dict | None:
        row = await self._session.execute(
            text(
                "SELECT role, organisation_id FROM core.org_memberships"
                " WHERE user_id = :uid ORDER BY"
                " CASE role"
                "   WHEN 'platform_admin' THEN 0"
                "   WHEN 'org_admin' THEN 1"
                "   WHEN 'auditor' THEN 2"
                "   WHEN 'analyst' THEN 3"
                "   ELSE 4 END"
                " LIMIT 1"
            ),
            {"uid": user_id},
        )
        rec = row.fetchone()
        if not rec:
            return None
        return {"role": rec[0], "org_id": rec[1]}

    # ID: 7f1e4c8b-2a3d-4f9c-b5e0-1d6a3c7f2e4b
    async def _log_event(
        self,
        event_type: str,
        *,
        user_id: UUID | None = None,
        actor_id: UUID | None = None,
        ip: str | None = None,
        ua: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        import json

        await self._session.execute(
            text(
                "INSERT INTO core.auth_events"
                " (user_id, event_type, actor_id, ip_address, user_agent, metadata)"
                " VALUES (:uid, :etype, :actor, :ip, :ua, :meta::jsonb)"
            ),
            {
                "uid": user_id,
                "etype": event_type,
                "actor": actor_id,
                "ip": ip,
                "ua": ua,
                "meta": json.dumps(metadata or {}),
            },
        )
