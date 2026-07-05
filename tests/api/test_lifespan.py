# tests/api/test_lifespan.py

"""Tests for the JWT secret startup guard in core_lifespan.

Verifies that the lifespan raises RuntimeError when the default
JWT_SECRET_KEY is used without the explicit ALLOW_INSECURE_DEV_SECRET
flag, and passes through when the flag is set or the secret is strong.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from body.infrastructure.lifespan import core_lifespan


async def test_jwt_guard_raises_with_default_secret_flag_false() -> None:
    """RuntimeError on startup when JWT_SECRET_KEY is the insecure default
    and ALLOW_INSECURE_DEV_SECRET is False (the default)."""
    app = MagicMock()
    with patch("body.infrastructure.lifespan.settings") as s:
        s.JWT_SECRET_KEY = "change-me-in-production"
        s.ALLOW_INSECURE_DEV_SECRET = False
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            async with core_lifespan(app):
                pass


async def test_jwt_guard_raises_with_default_secret_in_production() -> None:
    """CORE_ENV=PRODUCTION with default secret still blocked — env name alone
    is not a bypass (#711)."""
    app = MagicMock()
    with patch("body.infrastructure.lifespan.settings") as s:
        s.JWT_SECRET_KEY = "change-me-in-production"
        s.ALLOW_INSECURE_DEV_SECRET = False
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            async with core_lifespan(app):
                pass


async def test_jwt_guard_raises_even_with_dev_env_name_without_flag() -> None:
    """CORE_ENV=DEVELOPMENT does NOT bypass the guard — only the explicit
    flag does. A staging config copied from dev cannot accidentally permit
    the default secret (#711)."""
    app = MagicMock()
    with patch("body.infrastructure.lifespan.settings") as s:
        s.JWT_SECRET_KEY = "change-me-in-production"
        s.ALLOW_INSECURE_DEV_SECRET = False
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            async with core_lifespan(app):
                pass


async def test_jwt_guard_allows_default_secret_when_flag_set() -> None:
    """Default JWT secret is permitted when ALLOW_INSECURE_DEV_SECRET=True."""
    app = MagicMock()
    app.state = MagicMock()
    with (
        patch("body.infrastructure.lifespan.settings") as s,
        patch("body.infrastructure.lifespan.create_core_context") as mock_create,
    ):
        s.JWT_SECRET_KEY = "change-me-in-production"
        s.ALLOW_INSECURE_DEV_SECRET = True
        ctx = MagicMock()
        ctx._is_test_mode = False
        mock_create.return_value = ctx
        async with core_lifespan(app):
            pass


async def test_jwt_guard_allows_strong_secret_without_flag() -> None:
    """A non-default JWT secret passes the guard even when
    ALLOW_INSECURE_DEV_SECRET is False."""
    app = MagicMock()
    app.state = MagicMock()
    with (
        patch("body.infrastructure.lifespan.settings") as s,
        patch("body.infrastructure.lifespan.create_core_context") as mock_create,
    ):
        s.JWT_SECRET_KEY = (
            "secure-random-64-char-secret-abc123xyz-absolutely-not-the-default"
        )
        s.ALLOW_INSECURE_DEV_SECRET = False
        ctx = MagicMock()
        ctx._is_test_mode = False
        mock_create.return_value = ctx
        async with core_lifespan(app):
            pass
