# tests/body/services/test_coherence_service__close_run_if_empty.py

"""Integration test: CoherenceService.close_run_if_empty (issue #458).

Three cases:
  - a fresh run with zero candidates is closed (the gap the issue describes)
  - a run with at least one candidate is NOT closed (auto-close path owns it)
  - an already-closed run is a no-op (idempotent)

All three exercise the same WHERE clause on the live test DB so the
guard is real, not mocked.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.coherence_service import CoherenceService
from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Bind the registry to the test DB session factory."""
    service_registry.prime(get_session)


async def _run_status(session: AsyncSession, run_id: str) -> str:
    result = await session.execute(
        text("SELECT run_status FROM core.coherence_runs WHERE run_id = :rid"),
        {"rid": run_id},
    )
    row = result.fetchone()
    assert row is not None, f"run {run_id} not found"
    return row[0]


async def _delete_run(session: AsyncSession, run_id: str) -> None:
    await session.execute(
        text("DELETE FROM core.coherence_candidates WHERE run_id = :rid"),
        {"rid": run_id},
    )
    await session.execute(
        text("DELETE FROM core.coherence_runs WHERE run_id = :rid"),
        {"rid": run_id},
    )
    await session.commit()


async def test_zero_candidate_run_is_closed(db_session: AsyncSession) -> None:
    service = CoherenceService(db_session)
    run_id = await service.create_run(trigger="manual")
    try:
        assert await _run_status(db_session, run_id) == "open"

        closed = await service.close_run_if_empty(run_id)

        assert closed is True
        assert await _run_status(db_session, run_id) == "closed"
    finally:
        await _delete_run(db_session, run_id)


async def test_run_with_candidates_is_not_closed(db_session: AsyncSession) -> None:
    service = CoherenceService(db_session)
    run_id = await service.create_run(trigger="manual")
    try:
        await service.add_candidate(
            run_id=run_id,
            relation="R1_SCOPED",
            documents=["a.md", "b.md"],
            claim="a contradicts b",
            rationale="test fixture",
        )

        closed = await service.close_run_if_empty(run_id)

        assert closed is False
        assert await _run_status(db_session, run_id) == "open"
    finally:
        await _delete_run(db_session, run_id)


async def test_already_closed_run_is_noop(db_session: AsyncSession) -> None:
    service = CoherenceService(db_session)
    run_id = await service.create_run(trigger="manual")
    try:
        first_close = await service.close_run_if_empty(run_id)
        assert first_close is True
        assert await _run_status(db_session, run_id) == "closed"

        second_close = await service.close_run_if_empty(run_id)

        assert second_close is False
        assert await _run_status(db_session, run_id) == "closed"
    finally:
        await _delete_run(db_session, run_id)
