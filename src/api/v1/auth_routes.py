# src/api/v1/auth_routes.py
"""UAC auth endpoints (ADR-124).

All auth routes live under /auth/ (no /v1/ prefix — these are identity
infrastructure, not OEM API).  Tokens are delivered as httpOnly cookies;
the frontend never touches them in JavaScript.

Rate limiting is enforced in-process via a sliding-window counter.
This is adequate for single-process deployments; replace with Redis-backed
limiting if running multiple API workers.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, get_current_user, require_governor
from shared.config import settings
from shared.logger import getLogger
from will.governance.auth_runner import AuthLockedError, AuthRunner


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/auth", tags=["Auth"])

# ---------------------------------------------------------------------------
# In-process rate limiter (sliding window, per-IP)
# ---------------------------------------------------------------------------

_rate_lock = Lock()
_rate_buckets: dict[str, list[float]] = defaultdict(list)

_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "login": (10, 60),
    "register": (5, 60),
    "refresh": (60, 3600),
    "password_reset": (3, 3600),
}


# ID: 2b7e4c1f-9a3d-4f8c-b5e0-6d1a3c7f9e2b
def _check_rate(key: str, limit_key: str) -> None:
    max_calls, window_seconds = _RATE_LIMITS[limit_key]
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets[key]
        bucket[:] = [t for t in bucket if now - t < window_seconds]
        if len(bucket) >= max_calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )
        bucket.append(now)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

_SECURE = settings.CORE_ENV.upper() in {"PROD", "PRODUCTION"}


# ID: 5f9d2a7e-3c1b-4e8a-b0f6-4d2c1a5e9f7b
def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    response.set_cookie(
        "core_access",
        access_token,
        httponly=True,
        secure=_SECURE,
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        "core_refresh",
        refresh_token,
        httponly=True,
        secure=_SECURE,
        samesite="strict",
        path="/auth/refresh",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


# ID: 8a3f1c6e-2d4b-4a9c-b7e0-1f5d3a8c6f2e
def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("core_access")
    response.delete_cookie("core_refresh", path="/auth/refresh")


# ---------------------------------------------------------------------------
# Dependency: auth service instance
# ---------------------------------------------------------------------------


# ID: 1d6b4f9c-3e2a-4c8e-b0d7-5a1c3f6b9d4e
def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_api_session)],
) -> AuthRunner:
    """DI factory — constructs an AuthRunner for this request."""
    return AuthRunner(
        session=session,
        jwt_secret=settings.JWT_SECRET_KEY,
        access_expire_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
        resend_api_key=settings.RESEND_API_KEY,
        app_base_url=settings.APP_BASE_URL,
        mail_from=settings.MAIL_FROM,
    )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


# ID: c3737fa5-4055-4d1c-9fdc-e99229c1e02c
class RegisterRequest(BaseModel):
    """
    Request payload for new user registration.

    Defines the required and optional fields needed to create a user account,
    including support for organisation-scoped registration via an invitation token.

    Args:
        email: Verified email address of the registering user.
        password: Plaintext password to be securely hashed and stored.
        org_name: Optional name of an organisation to create and join.
        invitation_token: Optional token for joining an existing organisation.
    """

    email: EmailStr
    password: str
    org_name: str | None = None
    invitation_token: str | None = None


# ID: 5c1d9013-482a-40be-aee4-1cedc51d4058
class LoginRequest(BaseModel):
    """
    Represents a login authentication request from a client.

    Defines the expected schema for user-provided credentials
    submitted during the login process.

    Args:
        email: The user's email address, validated as a proper email format.
        password: The user's password in plain text for authentication.
    """

    email: EmailStr
    password: str


# ID: ec18c598-5202-4e32-ba63-2a6773b3c796
class PasswordResetRequest(BaseModel):
    """
    A data model representing a request to initiate a password reset.

    Validates that the provided email address conforms to the standard email format for downstream processing.

    Args:
        email: A valid email address for the target user account.
    """

    email: EmailStr


# ID: c97ee217-099e-483f-8454-05b57b634709
class PasswordResetConfirmRequest(BaseModel):
    """
    Request model for confirming a password reset with a verification token.

    Represents the required fields to complete a password reset flow —
    a cryptographic token proving authorization, and the new password to set.

    Args:
        token: Verification token obtained from the password reset initiation.
        new_password: The new password string to be set for the user account.
    """

    token: str
    new_password: str


# ID: 1c205eca-e484-44fd-a52d-3e1d0d228052
class PromoteRequest(BaseModel):
    """
    Request to promote a user to a new role within an organization.

    Args:
        user_id: The unique identifier of the user to be promoted.
        org_id: The organization context for the promotion (None for self-contained systems).
        role: The target role to assign (e.g. 'admin', 'moderator').
    """

    user_id: str
    org_id: str | None = None
    role: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
# ID: 4c9e2b7f-1a3d-4f8c-b5e0-2d6a1c4e9f7b
async def register(
    body: RegisterRequest,
    request: Request,
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Register a new user.  Returns a verification token to send via email."""
    _check_rate(request.client.host if request.client else "unknown", "register")
    try:
        result = await svc.register(
            email=str(body.email),
            password=body.password,
            org_name=body.org_name,
            invitation_token=body.invitation_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    email_sent = await svc.send_verification_email(
        str(body.email), result["email_verify_token"]
    )

    return {
        "user_id": result["user_id"],
        "message": "Registration successful. Check your email to verify your account.",
        **(
            {"_dev_verify_token": result["email_verify_token"]}
            if not email_sent
            and settings.CORE_ENV.upper() not in {"PROD", "PRODUCTION"}
            else {}
        ),
    }


@router.get("/verify-email")
# ID: 7e1f4b9c-2a3d-4c8e-b6f0-3d1a5c7e4f2b
async def verify_email(
    token: str,
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Verify email address via the token from the registration email."""
    try:
        await svc.verify_email(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"message": "Email verified. You may now log in."}


@router.post("/login")
# ID: 3b8d6c2f-1e4a-4f9c-b7a0-5c2d1a6e8f3b
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Authenticate and set httpOnly auth cookies."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    _check_rate(ip or "unknown", "login")

    try:
        tokens = await svc.login(str(body.email), body.password, ip=ip, ua=ua)
    except AuthLockedError as exc:
        retry_after = max(
            0, int((exc.locked_until - datetime.now(UTC)).total_seconds())
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to repeated failed login attempts.",
            headers={"Retry-After": str(retry_after)},
        )
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or account not active.",
        )

    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return {"message": "Login successful."}


@router.post("/refresh")
# ID: 9f4c2e7a-1b3d-4e8c-b5f0-6a2d1c9e4f7b
async def refresh(
    request: Request,
    response: Response,
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
    core_refresh: Annotated[str | None, Cookie()] = None,
) -> dict:
    """Exchange a valid refresh cookie for new access + refresh cookies (rotation)."""
    ip = request.client.host if request.client else "unknown"
    _check_rate(ip, "refresh")
    if not core_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token."
        )
    tokens = await svc.refresh(core_refresh)
    if not tokens:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalid or expired.",
        )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return {"message": "Token refreshed."}


@router.post("/logout")
# ID: 6d1a3c8f-5e2b-4f7c-b9a0-2c4d1a6e3f5b
async def logout(
    response: Response,
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
    core_refresh: Annotated[str | None, Cookie()] = None,
) -> dict:
    """Revoke refresh token and clear auth cookies."""
    if core_refresh:
        await svc.logout(core_refresh)
    _clear_auth_cookies(response)
    return {"message": "Logged out."}


# ID: 59bf7730-9228-49fe-9140-41bdd5b5ee06
class ChangePasswordRequest(BaseModel):
    """Request payload for an authenticated password change."""

    current_password: str
    new_password: str


@router.post("/change-password")
# ID: 7ddd819d-cf6d-4b14-9930-b360ef74d9f3
async def change_password(
    body: ChangePasswordRequest,
    user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Change the authenticated user's password.

    Verifies the current password before applying the change.
    Revokes all refresh tokens — caller must log in again.
    """
    try:
        ok = await svc.change_password(
            user_id=user["sub"],
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    return {"message": "Password changed. Please log in again."}


@router.post("/password-reset/request")
# ID: 2a5f8e1c-4b3d-4a9e-b7c0-1d5a3f8c2e4b
async def password_reset_request(
    body: PasswordResetRequest,
    request: Request,
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Request a password reset token (sent via email by the caller)."""
    _check_rate(str(body.email), "password_reset")
    raw_token = await svc.request_password_reset(str(body.email))

    email_sent = False
    if raw_token:
        email_sent = await svc.send_password_reset_email(str(body.email), raw_token)

    return {
        "message": "If that email is registered, a reset link will be sent.",
        **(
            {"_dev_reset_token": raw_token}
            if not email_sent
            and raw_token
            and settings.CORE_ENV.upper() not in {"PROD", "PRODUCTION"}
            else {}
        ),
    }


@router.post("/password-reset/confirm")
# ID: 8e3c1f6b-2a4d-4c9e-b5f0-7d1a3e8c6f2b
async def password_reset_confirm(
    body: PasswordResetConfirmRequest,
    response: Response,
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Apply a password reset and revoke all existing sessions."""
    try:
        ok = await svc.reset_password(body.token, body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token invalid or expired.",
        )
    _clear_auth_cookies(response)
    return {"message": "Password reset successful. Please log in again."}


@router.get("/me")
# ID: 5c7f2a9e-1d3b-4e8c-b6a0-4f2d1c5e7f3b
async def me(
    user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Return the current user's identity from their JWT (no DB hit)."""
    return {
        "user_id": user["sub"],
        "email": user["email"],
        "role": user["role"],
        "org_id": user["org_id"],
    }


# ---------------------------------------------------------------------------
# Admin — invite
# ---------------------------------------------------------------------------


# ID: 7acce499-3f53-47aa-aa96-e6210a161067
class InviteRequest(BaseModel):
    """
    Request model for inviting a user to an organization.

    Defines the constitutionally-governed data contract for processing
    user invitations, ensuring email validity and role assignment are
    enforced at the boundary layer before reaching business logic.

    Args:
        email: Validated email address of the invitee.
        role: Intended role assignment within the organization.
        org_id: Optional organization identifier; defaults to the
                acting user's organization if not specified.
    """

    email: EmailStr
    role: str
    org_id: str | None = None


@router.post("/invite", status_code=status.HTTP_201_CREATED)
# ID: 9b4e2f7c-1a3d-4c8e-b5f0-3d1a6c9e2f7b
async def invite(
    body: InviteRequest,
    user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Create an invitation link for a new user (ORG_ADMIN or PLATFORM_ADMIN)."""
    _ORG_ADMIN_MAX = {"visitor", "analyst", "auditor"}
    if user["role"] == "org_admin":
        if body.role not in _ORG_ADMIN_MAX:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ORG_ADMIN may only invite up to AUDITOR.",
            )
        target_org = body.org_id or user["org_id"]
        if target_org != user["org_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ORG_ADMIN may only invite into their own organisation.",
            )
    elif user["role"] != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions.",
        )
    else:
        target_org = body.org_id

    try:
        raw_token = await svc.create_invitation(
            email=str(body.email),
            org_id=target_org,
            role=body.role,
            created_by_id=user["sub"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    org_name = target_org or "CORE"
    email_sent = await svc.send_invitation_email(
        str(body.email), raw_token, body.role, org_name
    )

    return {
        "message": f"Invitation created for {body.email}.",
        **(
            {"_dev_invitation_token": raw_token}
            if not email_sent
            and settings.CORE_ENV.upper() not in {"PROD", "PRODUCTION"}
            else {}
        ),
    }


# ---------------------------------------------------------------------------
# Admin — promote / suspend
# ---------------------------------------------------------------------------


# ID: d41ea1b4-45b2-4c13-b91f-a1a6345dcf5d
class PromoteUserRequest(BaseModel):
    """
    Request payload for promoting a user to a new organizational role.

    Args:
        org_id: The unique identifier of the organization. May be None
                in system-level promotions.
        role: The target role to assign (e.g. 'admin', 'moderator').
    """

    org_id: str | None = None
    role: str


@router.post("/users/{user_id}/promote")
# ID: 4d8b2e9f-1c3a-4f7e-b5c0-6a2d1c8e4f3b
async def promote_user(
    user_id: str,
    body: PromoteUserRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Promote a user to a new role (ORG_ADMIN or PLATFORM_ADMIN only)."""
    try:
        await svc.promote_user(
            user_id=user_id,
            org_id=body.org_id or current_user["org_id"],
            role=body.role,
            promoted_by_id=current_user["sub"],
            promoter_role=current_user["role"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return {"message": f"User {user_id} promoted to {body.role}."}


@router.post("/users/{user_id}/suspend")
# ID: 7f1c4a9e-2d3b-4e8c-b6f0-1a5d3c7e2f4b
async def suspend_user(
    user_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
    _: Annotated[None, require_governor],
) -> dict:
    """Suspend a user account (PLATFORM_ADMIN only)."""
    await svc.set_active(user_id=user_id, active=False, actor_id=current_user["sub"])
    return {"message": f"User {user_id} suspended."}


@router.post("/users/{user_id}/reactivate")
# ID: 2e6c9f4b-1a3d-4c8e-b7f0-5d2a1c6e9f3b
async def reactivate_user(
    user_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
    _: Annotated[None, require_governor],
) -> dict:
    """Reactivate a suspended account (PLATFORM_ADMIN only)."""
    await svc.set_active(user_id=user_id, active=True, actor_id=current_user["sub"])
    return {"message": f"User {user_id} reactivated."}


# ---------------------------------------------------------------------------
# Admin — API keys
# ---------------------------------------------------------------------------


# ID: f8709a34-6a7a-4898-8085-9b7769cc1a4a
class CreateApiKeyRequest(BaseModel):
    """
    Request model for creating a new API key within the governed system.

    Captures the essential parameters needed to issue a constitutionally-bound
    API key: a human-readable label for identification, the access role that
    determines permission scope, and an optional expiration timestamp.

    Args:
        label: Human-readable name for the API key.
        role: Access role defining permission boundaries (default: "analyst").
        expires_at: ISO-format datetime string for key expiration, or None for no expiry.

    Returns:
        A validated CreateApiKeyRequest instance ready for policy enforcement.
    """

    label: str
    role: str = "analyst"
    expires_at: str | None = None


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
# ID: 5a3f8e2c-1b4d-4c9e-b7a0-6d1f3a5e8c2b
async def create_api_key(
    body: CreateApiKeyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Generate a new API key for the current user's organisation (ORG_ADMIN+)."""
    if current_user["role"] not in {"org_admin", "platform_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ORG_ADMIN or PLATFORM_ADMIN required.",
        )
    if not current_user.get("org_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No organisation associated with this account.",
        )
    try:
        result = await svc.create_api_key(
            org_id=current_user["org_id"],
            created_by_id=current_user["sub"],
            label=body.label,
            role=body.role,
            expires_at=body.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "key_id": result["key_id"],
        "label": body.label,
        "role": body.role,
        "raw_key": result["raw_key"],
        "message": "Store this key securely — it will not be shown again.",
    }


@router.get("/api-keys")
# ID: 8c1f4e7a-3d2b-4a9c-b5e0-2f6d1c4e8a3b
async def list_api_keys(
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """List active API keys for the current organisation (ORG_ADMIN+)."""
    if current_user["role"] not in {"org_admin", "platform_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ORG_ADMIN or PLATFORM_ADMIN required.",
        )
    if not current_user.get("org_id"):
        return {"keys": []}
    keys = await svc.list_api_keys(org_id=current_user["org_id"])
    return {"keys": keys}


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_200_OK)
# ID: 3b7e1c9f-4a2d-4f8e-b6c0-5d1a3f7e2c9b
async def revoke_api_key(
    key_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[AuthRunner, Depends(get_auth_service)],
) -> dict:
    """Revoke an API key (ORG_ADMIN+ within their own org)."""
    if current_user["role"] not in {"org_admin", "platform_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ORG_ADMIN or PLATFORM_ADMIN required.",
        )
    if not current_user.get("org_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No organisation."
        )
    ok = await svc.revoke_api_key(
        key_id=key_id,
        org_id=current_user["org_id"],
        actor_id=current_user["sub"],
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or already revoked.",
        )
    return {"message": f"API key {key_id} revoked."}
