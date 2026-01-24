# src/body/cli/workflows/phases/code_fixers_phase.py
"""Code fixing phase - IDs, headers, logging, docstrings, formatting."""

from __future__ import annotations

import time
from typing import Any

import typer
from rich.console import Console

from body.cli.commands.fix.code_style import fix_headers_internal
from body.cli.commands.fix.metadata import fix_ids_internal
from body.cli.commands.fix_logging import LoggingFixer
from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import fix_docstrings
from shared.action_types import ActionResult
from shared.context import CoreContext


# ID: 62bb1514-6702-40b0-bc18-1fce5d2852fd
class CodeFixersPhase:
    """Executes code fixing operations."""

    def __init__(
        self,
        core_context: CoreContext,
        reporter: DevSyncReporter,
        console: Console,
        write: bool,
        dry_run: bool,
    ):
        self.core_context = core_context
        self.reporter = reporter
        self.console = console
        self.write = write
        self.dry_run = dry_run

    # ID: aabce3d5-68c0-48dc-a17d-3f98b7b00bb8
    async def execute(self) -> None:
        """Execute all code fixing operations."""
        phase = self.reporter.start_phase("Code Fixers")

        # Fix IDs
        self.console.print("[cyan]Assigning stable IDs...[/cyan]")
        result = await fix_ids_internal(write=self.write)
        self.reporter.record_result(result, phase)
        if not result.ok:
            raise typer.Exit(1)

        # Fix Headers
        self.console.print("[cyan]Checking file headers...[/cyan]")
        result = await fix_headers_internal(write=self.write)
        self.reporter.record_result(result, phase)
        if not result.ok:
            raise typer.Exit(1)

        # Fix Logging
        await self._fix_logging(phase)

        # Fix Docstrings
        await self._fix_docstrings(phase)

        # Format Code
        await self._format_code(phase)

    async def _fix_logging(self, phase: Any) -> None:
        """Fix logging standards."""
        try:
            start = time.time()
            self.console.print("[cyan]Checking logging standards...[/cyan]")
            fixer = LoggingFixer(
                self.core_context.git_service.repo_path, dry_run=self.dry_run
            )
            fix_stats = fixer.fix_all()

            self.reporter.record_result(
                ActionResult(
                    action_id="fix.logging",
                    ok=True,
                    data=fix_stats,
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="fix.logging",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            self.console.print("[yellow]⚠️  Logging fix issues, continuing...[/yellow]")

    async def _fix_docstrings(self, phase: Any) -> None:
        """Fix missing docstrings."""
        try:
            start = time.time()
            self.console.print("[cyan]Checking docstrings...[/cyan]")
            await fix_docstrings(context=self.core_context, write=self.write)

            self.reporter.record_result(
                ActionResult(
                    action_id="fix.docstrings",
                    ok=True,
                    data={"status": "completed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="fix.docstrings",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)

    async def _format_code(self, phase: Any) -> None:
        """Format code with Black/Ruff."""
        try:
            start = time.time()
            self.console.print("[cyan]Formatting code...[/cyan]")
            format_code()

            self.reporter.record_result(
                ActionResult(
                    action_id="fix.code-style",
                    ok=True,
                    data={"status": "completed"},
                    duration_sec=time.time() - start,
                ),
                phase,
            )
        except Exception as e:
            self.reporter.record_result(
                ActionResult(
                    action_id="fix.code-style",
                    ok=False,
                    data={"error": str(e)},
                ),
                phase,
            )
            raise typer.Exit(1)
