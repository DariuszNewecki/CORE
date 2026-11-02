"""ConfigService refuses a database without its system_config row (#1390 G5).

schema.sql and migration 20261102_1390 create the row, so its absence means
the database skipped migrations; defaulting LLM_ENABLED to false hid that.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.infrastructure.config_service import ConfigService


def _db(sysrow: dict | None) -> MagicMock:
    resources = MagicMock()
    resources.mappings.return_value = []
    system = MagicMock()
    system.mappings.return_value.fetchone.return_value = sysrow
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[resources, system])
    return db


async def test_missing_system_config_row_is_refused() -> None:
    with pytest.raises(RuntimeError, match=r"core\.system_config has no row"):
        await ConfigService.create(_db(None))


async def test_row_values_reach_the_cache() -> None:
    row = {
        "llm_enabled": False,
        "request_timeout_seconds": 300,
        "embed_model_revision": None,
    }
    config = await ConfigService.create(_db(row))
    assert await config.get("LLM_ENABLED") == "false"
