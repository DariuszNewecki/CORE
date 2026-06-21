# src/body/services/auth/tokens.py
"""JWT access tokens and opaque refresh token helpers (ADR-124).

Access tokens  — short-lived JWTs (HS256).  Stateless; no DB row.
Refresh tokens — opaque random strings stored *hashed* in core.refresh_tokens.
                 Revocable at logout / account suspension.

Email-verification tokens — short-lived JWTs with type="email_verify".
                            No DB row needed; mail link is naturally single-use
                            because verifying sets email_verified=true.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt


_ALGORITHM = "HS256"


# ID: c2e8f4a1-9b3d-4f7c-8e1a-6d2b5c0f9e3a
def create_access_token(
    user_id: str,
    email: str,
    role: str,
    org_id: str | None,
    secret: str,
    expire_minutes: int = 60,
) -> str:
    """Issue a signed JWT access token."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "org_id": org_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


# ID: 5a9d3b7e-2f1c-4e8a-b6d0-1c4f7a2e9b5d
def decode_access_token(token: str, secret: str) -> dict:
    """Decode and verify a JWT access token.  Raises jwt.* on failure."""
    payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


# ID: 8f2e1c6b-4a3d-4f9c-a7e0-3b5d2c1f8a4e
def create_email_verify_token(user_id: str, secret: str) -> str:
    """Issue a short-lived JWT for email verification (24 h)."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "email_verify",
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


# ID: 1d7b4f9e-3c2a-4e8b-9f1d-6a5c0e2b7f3d
def decode_email_verify_token(token: str, secret: str) -> str:
    """Decode email-verify JWT and return user_id.  Raises on failure."""
    payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    if payload.get("type") != "email_verify":
        raise jwt.InvalidTokenError("not an email_verify token")
    return str(payload["sub"])


# ID: 4e6a2d9c-7f1b-4c3e-8a0d-2b5f1c4e7a9d
def generate_opaque_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex_hash) for refresh / reset tokens.

    The raw token is sent to the client; only the hash is stored in the DB.
    """
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


# ID: 9c3f1a7e-2d4b-4e6c-b0f8-5a1d3c7e2f9b
def hash_token(raw: str) -> str:
    """Hash a raw opaque token for DB lookup."""
    return hashlib.sha256(raw.encode()).hexdigest()
