"""Unit tests for `_print_coherence_advisory` (ADR-067 D5).

The helper appends one advisory line to `core-admin code audit` output.
Three branches per ADR-067 D5:

  - No coherence runs exist:          "no runs recorded — ..."
  - At least one run is still open:   "{N} open run(s) · {M} candidate(s) unreviewed"
  - All runs closed:                  "clean (last run YYYY-MM-DD)"

Tests drive a Mock(spec=CoherenceService) and capture Rich output via a
StringIO-backed Console. No DB, no live service.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console

from body.services.coherence_service import CoherenceService
from cli.resources.code.audit import _print_coherence_advisory


def _capture_console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return (
        Console(file=buf, force_terminal=False, width=200, no_color=True),
        buf,
    )


@pytest.mark.asyncio
async def test_advisory_no_runs_recorded():
    service = Mock(spec=CoherenceService)
    service.get_unreviewed_summary = AsyncMock(
        return_value={"open_runs": 0, "unreviewed": 0}
    )
    service.get_latest_run = AsyncMock(return_value=None)

    console, buf = _capture_console()
    await _print_coherence_advisory(console, service)

    out = buf.getvalue()
    assert "Constitutional Coherence: no runs recorded" in out
    assert "core-admin coherence check --full" in out


@pytest.mark.asyncio
async def test_advisory_open_runs_reports_counts():
    service = Mock(spec=CoherenceService)
    service.get_unreviewed_summary = AsyncMock(
        return_value={"open_runs": 2, "unreviewed": 17}
    )
    # latest must be non-None so the branch reaches the open-runs check.
    service.get_latest_run = AsyncMock(
        return_value={"run_id": "x", "run_at": datetime(2026, 5, 22, tzinfo=UTC)}
    )

    console, buf = _capture_console()
    await _print_coherence_advisory(console, service)

    out = buf.getvalue()
    assert "Constitutional Coherence: 2 open run(s)" in out
    assert "17 candidate(s) unreviewed" in out
    # The closed-branch wording must not appear in the open-runs case.
    assert "clean" not in out


@pytest.mark.asyncio
async def test_advisory_all_closed_reports_clean_with_date():
    service = Mock(spec=CoherenceService)
    service.get_unreviewed_summary = AsyncMock(
        return_value={"open_runs": 0, "unreviewed": 0}
    )
    service.get_latest_run = AsyncMock(
        return_value={
            "run_id": "x",
            "run_at": datetime(2026, 5, 22, 14, 47, 1, tzinfo=UTC),
        }
    )

    console, buf = _capture_console()
    await _print_coherence_advisory(console, service)

    out = buf.getvalue()
    assert "Constitutional Coherence: clean (last run 2026-05-22)" in out
