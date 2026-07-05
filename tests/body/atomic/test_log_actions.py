# tests/body/atomic/test_log_actions.py
"""Tests for log_actions atomic actions (ADR-052).

Covers:
- _cutoff_month: correct (year, month) arithmetic.
- _parse_partition_month: extracts year/month from relname; rejects bad names.
- action_maintain_log_partitions: dry-run returns planned partition list.
- action_archive_log_partitions: dry-run with mocked pg_catalog returns candidates.
- action_archive_log_partitions: write mode archives candidates (mocked session).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.atomic.log_actions import (
    _cutoff_month,
    _parse_partition_month,
    action_archive_log_partitions,
    action_maintain_log_partitions,
)
from shared.governance_token import authorize_execution


# ── _cutoff_month ─────────────────────────────────────────────────────────────


# ID: 3e7aad96-fb14-4e4b-9073-ec3a6dbe67ae
def test_cutoff_month_basic() -> None:
    """cutoff_month subtracts retention_months from today correctly."""
    with patch("body.atomic.log_actions.date") as mock_date:
        mock_date.today.return_value = date(2026, 7, 5)
        year, month = _cutoff_month(24)
    assert (year, month) == (2024, 7)


# ID: 4b3cc7b9-8b3f-45e5-8ba1-a9ed6e6bc7a4
def test_cutoff_month_year_boundary() -> None:
    """cutoff_month rolls across year boundaries correctly."""
    with patch("body.atomic.log_actions.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 1)
        year, month = _cutoff_month(6)
    assert (year, month) == (2025, 9)


# ID: 1b0db265-3c52-4af8-b7aa-b1c34ccf553b
def test_cutoff_month_zero_retention() -> None:
    """cutoff_month with retention=0 returns the current month."""
    with patch("body.atomic.log_actions.date") as mock_date:
        mock_date.today.return_value = date(2026, 7, 5)
        year, month = _cutoff_month(0)
    assert (year, month) == (2026, 7)


# ── _parse_partition_month ────────────────────────────────────────────────────


# ID: 8e9c3ef5-0fa9-441b-8b29-00e5b82c3f0e
def test_parse_partition_month_valid() -> None:
    """Extracts (year, month) from standard partition relname."""
    assert _parse_partition_month("llm_exchange_log_2026_05") == (2026, 5)


# ID: a0f5b39c-72bc-4da9-8e1b-5b29e498b2dc
def test_parse_partition_month_invalid_format() -> None:
    """Returns None for names that do not match the expected pattern."""
    assert _parse_partition_month("llm_exchange_log") is None
    assert _parse_partition_month("some_other_table_2026_05") is None
    assert _parse_partition_month("llm_exchange_log_2026") is None


# ── action_maintain_log_partitions (dry-run) ──────────────────────────────────


# ID: c6b8adcb-9e59-4d63-a8f8-b25cd9c63f57
@pytest.mark.asyncio
async def test_maintain_log_partitions_dry_run_returns_planned() -> None:
    """Dry-run returns ok=True with a non-empty list of planned partitions."""
    ctx = MagicMock()
    with (
        patch("body.atomic.log_actions.date") as mock_date,
        authorize_execution("log.maintain_partitions"),
    ):
        mock_date.today.return_value = date(2026, 7, 5)
        result = await action_maintain_log_partitions(
            core_context=ctx, write=False, advance_months=2
        )

    assert result.ok is True
    assert result.data["dry_run"] is True
    assert result.data["advance_months"] == 2
    planned = result.data["planned"]
    assert "core.llm_exchange_log_2026_08" in planned
    assert "core.llm_exchange_log_2026_09" in planned
    assert len(planned) == 2


# ── action_archive_log_partitions (dry-run) ───────────────────────────────────


def _make_session_with_partitions(relnames: list[str]) -> MagicMock:
    """Return an async context-manager mock that yields a session returning relnames."""
    rows_mock = MagicMock()
    rows_mock.fetchall.return_value = [(r,) for r in relnames]

    session = AsyncMock()
    session.execute = AsyncMock(return_value=rows_mock)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ID: d71e86c3-b4cf-4ca9-9e02-e28ee2ef5d46
@pytest.mark.asyncio
async def test_archive_log_partitions_dry_run_no_candidates() -> None:
    """Dry-run with all partitions newer than cutoff returns empty candidates."""
    ctx = MagicMock()
    # All partitions are in 2026 — cutoff with retention=24 is 2024-07, so none qualify
    session_cm = _make_session_with_partitions([
        "llm_exchange_log_2026_05",
        "llm_exchange_log_2026_06",
    ])
    with (
        patch("body.atomic.log_actions.get_session", return_value=session_cm),
        patch("body.atomic.log_actions.date") as mock_date,
        authorize_execution("log.archive_partitions"),
    ):
        mock_date.today.return_value = date(2026, 7, 5)
        result = await action_archive_log_partitions(
            core_context=ctx, write=False, retention_months=24
        )

    assert result.ok is True
    assert result.data["dry_run"] is True
    assert result.data["candidates"] == []
    assert result.data["cutoff"] == "2024-07"


# ID: f40d97aa-6a12-40cd-8481-3e3b18a783df
@pytest.mark.asyncio
async def test_archive_log_partitions_dry_run_with_candidates() -> None:
    """Dry-run identifies partitions older than cutoff as candidates."""
    ctx = MagicMock()
    session_cm = _make_session_with_partitions([
        "llm_exchange_log_2024_01",
        "llm_exchange_log_2024_06",
        "llm_exchange_log_2026_07",
    ])
    with (
        patch("body.atomic.log_actions.get_session", return_value=session_cm),
        patch("body.atomic.log_actions.date") as mock_date,
        authorize_execution("log.archive_partitions"),
    ):
        mock_date.today.return_value = date(2026, 7, 5)
        result = await action_archive_log_partitions(
            core_context=ctx, write=False, retention_months=24
        )

    assert result.ok is True
    assert set(result.data["candidates"]) == {
        "llm_exchange_log_2024_01",
        "llm_exchange_log_2024_06",
    }


# ── action_archive_log_partitions (write mode) ────────────────────────────────


# ID: e8f22f16-f20f-4a5f-ae97-cbbce5b21eda
@pytest.mark.asyncio
async def test_archive_log_partitions_write_archives_candidates() -> None:
    """Write mode executes DETACH + SET SCHEMA DDL for each candidate."""
    ctx = MagicMock()

    # First get_session call: read pg_inherits (dry-run discovery phase)
    discovery_cm = _make_session_with_partitions(["llm_exchange_log_2024_01"])

    # Second get_session call: DDL execution
    ddl_session = AsyncMock()
    ddl_session.execute = AsyncMock()
    ddl_session.commit = AsyncMock()
    ddl_session.rollback = AsyncMock()
    ddl_cm = MagicMock()
    ddl_cm.__aenter__ = AsyncMock(return_value=ddl_session)
    ddl_cm.__aexit__ = AsyncMock(return_value=False)

    call_count = 0

    def _session_factory() -> MagicMock:
        nonlocal call_count
        call_count += 1
        return discovery_cm if call_count == 1 else ddl_cm

    with (
        patch("body.atomic.log_actions.get_session", side_effect=_session_factory),
        patch("body.atomic.log_actions.date") as mock_date,
        authorize_execution("log.archive_partitions"),
    ):
        mock_date.today.return_value = date(2026, 7, 5)
        result = await action_archive_log_partitions(
            core_context=ctx, write=True, retention_months=24
        )

    assert result.ok is True
    assert result.data["dry_run"] is False
    assert "llm_exchange_log_2024_01" in result.data["archived"]
    assert result.data["errors"] == []
    # Verify DDL was executed (CREATE SCHEMA + 2 ALTER TABLE calls)
    assert ddl_session.execute.call_count >= 3
