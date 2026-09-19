"""Tests for `core-admin database status` (src/cli/resources/database/status.py).

Calls the undecorated function directly (`database_status.__wrapped__`), same
pattern as tests/cli/resources/vectors/test_rebuild.py, since `ctx` is never
read in the body and core_command's wrapper isn't under test here.

#841: --format json must emit pure parseable JSON on stdout. Two distinct
defects existed: (1) a Rich heading printed unconditionally before the format
check, and (2) the JSON payload itself was emitted via `console.print`, whose
markup parser silently strips bracket-like content and whose line-wrapping
can insert literal newlines into long values -- either corrupts or
invalidates the JSON. Table mode's existing Rich rendering must be preserved
unchanged.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import typer

from cli.resources.database.status import database_status
from shared.infrastructure.repositories.db.status_service import StatusReport


def _report(
    *,
    connected: bool = True,
    version: str | None = "17.2",
    applied: set[str] | None = None,
    pending: list[str] | None = None,
) -> StatusReport:
    return StatusReport(
        is_connected=connected,
        db_version=version,
        applied_migrations=applied if applied is not None else {"0001_init"},
        pending_migrations=pending if pending is not None else [],
    )


async def test_json_output_is_pure_parseable_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch(
        "shared.infrastructure.repositories.db.status_service.status",
        return_value=_report(),
    ):
        await database_status.__wrapped__(None, detailed=False, format="json")
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["connected"] is True
    assert parsed["version"] == "17.2"
    assert parsed["applied_migrations"] == ["0001_init"]
    assert parsed["pending_migrations"] == []
    assert "Database Status" not in captured.out


async def test_json_output_survives_bracket_and_long_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression for the Rich console.print corruption this issue traced.

    Bracket-like content used to be silently stripped by Rich's markup
    parser, and long values used to be line-wrapped mid-string -- both
    reproduced directly against `console.print(json.dumps(...))` before this
    fix. Raw sys.stdout.write avoids both failure modes.
    """
    long_migration = "m" * 200
    with (
        patch(
            "shared.infrastructure.repositories.db.status_service.status",
            return_value=_report(
                version="[not-a-markup-tag] 17.2",
                pending=[long_migration],
            ),
        ),
        pytest.raises(typer.Exit) as exc_info,  # pending -> exit 2 (ADR-162)
    ):
        await database_status.__wrapped__(None, detailed=False, format="json")
    assert exc_info.value.exit_code == 2
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["version"] == "[not-a-markup-tag] 17.2"
    assert parsed["pending_migrations"] == [long_migration]
    assert parsed["current"] is False


async def test_table_mode_still_prints_header_and_tables(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch(
            "shared.infrastructure.repositories.db.status_service.status",
            return_value=_report(pending=["0002_add_col"]),
        ),
        pytest.raises(typer.Exit) as exc_info,  # pending -> exit 2 (ADR-162)
    ):
        await database_status.__wrapped__(None, detailed=False, format="table")
    assert exc_info.value.exit_code == 2
    captured = capsys.readouterr()
    assert "Database Status" in captured.out
    assert "Connection" in captured.out
    assert "Migrations" in captured.out
    assert "0002_add_col" in captured.out


# ── ADR-162 D2/D3: read-only status reports contradictions and baselines ─────


async def test_current_database_exits_zero_and_reports_current() -> None:
    with patch(
        "shared.infrastructure.repositories.db.status_service.status",
        return_value=_report(),
    ):
        await database_status.__wrapped__(None, detailed=False, format="json")


async def test_probe_failures_are_reported_and_exit_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = _report()
    report.probe_failures = ["0001_init"]
    with (
        patch(
            "shared.infrastructure.repositories.db.status_service.status",
            return_value=report,
        ),
        pytest.raises(typer.Exit) as exc_info,
    ):
        await database_status.__wrapped__(None, detailed=False, format="table")
    assert exc_info.value.exit_code == 2
    out = capsys.readouterr().out
    assert "contradiction" in out and "0001_init" in out


async def test_empty_ledger_suggests_a_baseline_without_recording(
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = _report(applied=set(), pending=["0001_init"])
    report.baseline_suggestion = "v2.9.1"
    with (
        patch(
            "shared.infrastructure.repositories.db.status_service.status",
            return_value=report,
        ),
        pytest.raises(typer.Exit) as exc_info,
    ):
        await database_status.__wrapped__(None, detailed=False, format="json")
    assert exc_info.value.exit_code == 2
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["baseline_suggestion"] == "v2.9.1"
    assert parsed["applied_migrations"] == []
    assert parsed["current"] is False


async def test_json_mode_error_emits_json_error_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch(
        "shared.infrastructure.repositories.db.status_service.status",
        side_effect=RuntimeError("connection refused"),
    ):
        with pytest.raises(typer.Exit) as exc_info:
            await database_status.__wrapped__(None, detailed=False, format="json")
    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["connected"] is False
    assert "connection refused" in parsed["error"]


async def test_table_mode_error_still_prints_rich_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch(
        "shared.infrastructure.repositories.db.status_service.status",
        side_effect=RuntimeError("connection refused"),
    ):
        with pytest.raises(typer.Exit) as exc_info:
            await database_status.__wrapped__(None, detailed=False, format="table")
    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Database Status" in captured.out
    assert "Error" in captured.out
    assert "connection refused" in captured.out
