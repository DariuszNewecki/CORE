# tests/body/maintenance/scripts/test_context_export__db_schema.py

"""ContextExporter._export_db_schema runs pg_dump through subprocess_utils."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from body.maintenance.scripts import context_export
from body.maintenance.scripts.context_export import ContextExporter
from shared.utils.subprocess_utils import SubprocessResult


def _exporter() -> ContextExporter:
    exporter = ContextExporter.__new__(ContextExporter)
    exporter._context = SimpleNamespace(  # type: ignore[assignment]
        settings=SimpleNamespace(DATABASE_URL="postgresql://u@h/db")
    )
    exporter.fh = MagicMock()
    exporter.export_rel_dir = "var/exports/core_export_x"
    return exporter


async def test_pg_dump_output_is_written_with_trailing_newline() -> None:
    exporter = _exporter()
    run = AsyncMock(return_value=SubprocessResult("CREATE TABLE t ();", "", 0))
    with patch.object(context_export, "run_command_async", run):
        await exporter._export_db_schema()

    run.assert_awaited_once_with(
        ["pg_dump", "--schema-only", "--no-owner", "postgresql://u@h/db"]
    )
    exporter.fh.write_runtime_text.assert_called_once_with(
        "var/exports/core_export_x/db_schema.sql", "CREATE TABLE t ();\n"
    )


async def test_empty_pg_dump_output_writes_nothing() -> None:
    exporter = _exporter()
    run = AsyncMock(return_value=SubprocessResult("", "pg_dump: error", 1))
    with patch.object(context_export, "run_command_async", run):
        await exporter._export_db_schema()

    exporter.fh.write_runtime_text.assert_not_called()


async def test_missing_pg_dump_is_logged_not_raised() -> None:
    exporter = _exporter()
    run = AsyncMock(side_effect=FileNotFoundError("pg_dump"))
    with patch.object(context_export, "run_command_async", run):
        await exporter._export_db_schema()

    exporter.fh.write_runtime_text.assert_not_called()
