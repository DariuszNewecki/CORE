# tests/test_smoke_runtime.py

from __future__ import annotations

import os

from shared.config import settings


def test_smoke_env_loaded_and_test_mode() -> None:
    """
    Baseline harness check:
    - pytest-dotenv loaded `.env.test`
    - CORE_ENV is TEST (or at minimum not PROD)
    - DATABASE_URL is present
    """
    core_env = os.getenv("CORE_ENV")
    assert (
        core_env is not None
    ), "CORE_ENV is not set (pytest-dotenv may not be loading .env.test)"
    assert core_env.upper() == "TEST", f"Expected CORE_ENV=TEST, got {core_env!r}"

    db_url = os.getenv("DATABASE_URL")
    assert db_url, "DATABASE_URL missing (pytest-dotenv may not be loading .env.test)"

    # This is a safety invariant in your harness: tests must never hit non-test DBs.
    assert (
        "core_test" in db_url
    ), f"Refusing to accept non-test DATABASE_URL in tests: {db_url!r}"

    # Settings should be initialized for test session by conftest autouse fixture.
    # We avoid deep coupling: just verify the repo path is sane and non-empty.
    assert (
        getattr(settings, "REPO_PATH", None) is not None
    ), "settings.REPO_PATH not initialized"
