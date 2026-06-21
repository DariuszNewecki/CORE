# tests/body/services/auth/test_auth_password_and_tokens.py
"""Unit tests for password hashing and token helpers (ADR-124).

No DB required — pure in-process functions only.
"""
from __future__ import annotations

import time

import jwt
import pytest

from body.services.auth.password import hash_password, verify_password
from body.services.auth.tokens import (
    create_access_token,
    create_email_verify_token,
    decode_access_token,
    decode_email_verify_token,
    generate_opaque_token,
    hash_token,
)


_SECRET = "test-secret-key-not-for-production"


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------


def test_hash_is_not_plaintext() -> None:
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"
    assert hashed.startswith("$2b$")


def test_verify_correct_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", hashed) is False


# ---------------------------------------------------------------------------
# Access tokens
# ---------------------------------------------------------------------------


def test_create_and_decode_access_token() -> None:
    token = create_access_token(
        user_id="abc-123",
        email="user@example.com",
        role="analyst",
        org_id="org-999",
        secret=_SECRET,
        expire_minutes=60,
    )
    payload = decode_access_token(token, _SECRET)
    assert payload["sub"] == "abc-123"
    assert payload["email"] == "user@example.com"
    assert payload["role"] == "analyst"
    assert payload["org_id"] == "org-999"
    assert payload["type"] == "access"


def test_access_token_wrong_secret_raises() -> None:
    token = create_access_token("u1", "a@b.com", "visitor", None, _SECRET)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token, "wrong-secret")


def test_access_token_expired_raises() -> None:
    token = create_access_token("u1", "a@b.com", "visitor", None, _SECRET, expire_minutes=0)
    time.sleep(1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, _SECRET)


# ---------------------------------------------------------------------------
# Email verification tokens
# ---------------------------------------------------------------------------


def test_email_verify_token_roundtrip() -> None:
    token = create_email_verify_token("user-uuid-123", _SECRET)
    user_id = decode_email_verify_token(token, _SECRET)
    assert user_id == "user-uuid-123"


def test_email_verify_token_wrong_type_rejected() -> None:
    access = create_access_token("u1", "a@b.com", "visitor", None, _SECRET)
    with pytest.raises(jwt.InvalidTokenError):
        decode_email_verify_token(access, _SECRET)


# ---------------------------------------------------------------------------
# Opaque tokens
# ---------------------------------------------------------------------------


def test_generate_opaque_token_returns_pair() -> None:
    raw, hashed = generate_opaque_token()
    assert len(raw) > 20
    assert len(hashed) == 64


def test_generate_opaque_token_is_unique() -> None:
    pairs = {generate_opaque_token()[0] for _ in range(10)}
    assert len(pairs) == 10


def test_hash_token_is_deterministic() -> None:
    raw, hashed = generate_opaque_token()
    assert hash_token(raw) == hashed
