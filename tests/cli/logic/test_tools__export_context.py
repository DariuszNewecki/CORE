# tests/cli/logic/test_tools__export_context.py
"""`tools export-context` actually runs the exporter.

It used to call the async `context_export.main()` without awaiting it, so
the export never happened.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import typer

from cli.logic.tools import export_context_cmd


# ID: 3c019aeb-75cd-447d-af52-637dd94aaf39
async def test_export_context_awaits_exporter_with_cli_context() -> None:
    core_context = MagicMock(name="core_context")
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = core_context
    exporter = MagicMock()
    exporter.run = AsyncMock(return_value="var/exports/core_export_x")

    with patch(
        "cli.logic.tools.context_export.ContextExporter", return_value=exporter
    ) as exporter_cls:
        await export_context_cmd(ctx)

    exporter_cls.assert_called_once_with(context=core_context)
    exporter.run.assert_awaited_once()
