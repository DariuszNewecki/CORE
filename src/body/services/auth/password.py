# src/body/services/auth/password.py
"""Password hashing helpers (ADR-124).

Uses passlib's bcrypt context — cost factor 12 (strong enough for passwords,
fast enough not to be a DoS vector on the login endpoint).
"""

from __future__ import annotations

from passlib.context import CryptContext


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ID: a3f1c820-4e7d-4b2a-9c15-8d6e2f0a1b3c
def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return _pwd_context.hash(plain)


# ID: 7b4d9e62-1f3a-4c8b-a027-5e9f2d1c6a84
def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return _pwd_context.verify(plain, hashed)
