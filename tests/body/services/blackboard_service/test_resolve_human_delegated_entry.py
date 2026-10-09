# tests/body/services/blackboard_service/test_resolve_human_delegated_entry.py

"""#926 -- the governor can close an 'open' finding delegated to a human.

`workers resolve` (resolve_indeterminate_entry) only matched status
'indeterminate'. A writer's tripped safety guard (ADR-070 D8,
coherence.repo_artifacts.drift) posts status 'open' with
resolution_mechanism 'human' and waits for governor inspection; once the
governor had acted there was no way to close it. The UPDATE now also matches
open + human, and nothing else: an ordinary open finding stays out of reach.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.services.blackboard_service.blackboard_service import BlackboardService


async def _resolve_sql() -> str:
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=1))

    @asynccontextmanager
    async def _begin():
        yield

    @asynccontextmanager
    async def _session():
        yield session

    session.begin = _begin
    with patch("body.services.service_registry.ServiceRegistry.session", new=_session):
        updated = await BlackboardService().resolve_indeterminate_entry(
            entry_id="00000000-0000-0000-0000-000000000001", reason="r"
        )
    assert updated == 1
    return " ".join(str(session.execute.await_args.args[0]).split())


@pytest.mark.asyncio
async def test_matches_indeterminate_and_open_human_only() -> None:
    sql = await _resolve_sql()
    assert (
        "AND ( status = 'indeterminate' "
        "OR (status = 'open' AND resolution_mechanism = 'human') )" in sql
    )


@pytest.mark.asyncio
async def test_still_stamps_resolution_attribution() -> None:
    sql = await _resolve_sql()
    assert "SET status = 'resolved'" in sql
    assert "'resolution_authority', cast(:authority as text)" in sql
