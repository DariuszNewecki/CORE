# tests/api/test_lifespan.py

"""Tests for the JWT secret startup guard in core_lifespan.

Verifies that the lifespan raises RuntimeError when the default
JWT_SECRET_KEY is used outside a dev/test environment, and passes
through correctly for strong secrets or safe environments.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from body.infrastructure.lifespan import core_lifespan


async def test_jwt_guard_raises_with_default_secret_in_production() -> None:
    """RuntimeError on startup when JWT_SECRET_KEY is the insecure default
    and CORE_ENV is not DEV/DEVELOPMENT/TEST."""
    app = MagicMock()
    with patch("body.infrastructure.lifespan.settings") as s:
        s.JWT_SECRET_KEY = "change-me-in-production"
        s.CORE_ENV = "PRODUCTION"
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            async with core_lifespan(app):
                pass


async def test_jwt_guard_raises_with_default_secret_in_staging() -> None:
    """Staging is not a safe env — default secret still blocked."""
    app = MagicMock()
    with patch("body.infrastructure.lifespan.settings") as s:
        s.JWT_SECRET_KEY = "change-me-in-production"
        s.CORE_ENV = "STAGING"
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            async with core_lifespan(app):
                pass


@pytest.mark.parametrize("env", ["DEV", "DEVELOPMENT", "TEST", "dev", "development", "test"])
async def test_jwt_guard_allows_default_secret_in_safe_envs(env: str) -> None:
    """Default JWT secret is permitted for DEV / DEVELOPMENT / TEST (case-insensitive)."""
    app = MagicMock()
    app.state = MagicMock()
    with (
        patch("body.infrastructure.lifespan.settings") as s,
        patch("body.infrastructure.lifespan.create_core_context") as mock_create,
    ):
        s.JWT_SECRET_KEY = "change-me-in-production"
        s.CORE_ENV = env
        ctx = MagicMock()
        ctx._is_test_mode = False
        mock_create.return_value = ctx
        async with core_lifespan(app):
            pass


async def test_jwt_guard_allows_strong_secret_in_production() -> None:
    """A non-default JWT secret passes the guard even in production."""
    app = MagicMock()
    app.state = MagicMock()
    with (
        patch("body.infrastructure.lifespan.settings") as s,
        patch("body.infrastructure.lifespan.create_core_context") as mock_create,
    ):
        s.JWT_SECRET_KEY = "secure-random-64-char-secret-abc123xyz-absolutely-not-the-default"
        s.CORE_ENV = "PRODUCTION"
        ctx = MagicMock()
        ctx._is_test_mode = False
        mock_create.return_value = ctx
        async with core_lifespan(app):
            pass
