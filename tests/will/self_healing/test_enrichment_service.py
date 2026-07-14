# tests/will/self_healing/test_enrichment_service.py
"""Guard: the 'enrich symbols' per-run cap is a governed knob, not a literal.

The batch size for `_get_symbols_to_enrich` was a hardcoded `LIMIT 200`
inside the SQL string; #774 (ADR-040 sweep) moved it to
operational_config.yaml `misc.enrichment_symbols_batch_limit` and binds it as
a query parameter. These tests prove the value is sourced from config and
actually reaches the query, so a future YAML change alone re-tunes the run.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.infrastructure.intent.operational_config import load_operational_config
from will.self_healing.enrichment_service import _get_symbols_to_enrich


@pytest.mark.asyncio
async def test_batch_limit_bound_from_operational_config() -> None:
    """`_get_symbols_to_enrich` binds misc.enrichment_symbols_batch_limit."""
    expected = load_operational_config().misc.enrichment_symbols_batch_limit

    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    session = AsyncMock()
    session.execute.return_value = result

    await _get_symbols_to_enrich(session)

    session.execute.assert_awaited_once()
    _, params = session.execute.await_args.args
    assert params == {"batch_limit": expected}
