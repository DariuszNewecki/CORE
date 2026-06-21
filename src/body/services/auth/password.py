# src/body/services/auth/password.py
"""Password hashing helpers (ADR-124 D4).

Uses argon2id via argon2-cffi — parameters match OWASP minimum recommendations:
  memory_cost=65536 (64 MiB), time_cost=3, parallelism=1.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


_ph = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=1)


# ID: a3f1c820-4e7d-4b2a-9c15-8d6e2f0a1b3c
def hash_password(plain: str) -> str:
    """Return an argon2id hash of *plain*."""
    return _ph.hash(plain)


# ID: 7b4d9e62-1f3a-4c8b-a027-5e9f2d1c6a84
def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    try:
        _ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
