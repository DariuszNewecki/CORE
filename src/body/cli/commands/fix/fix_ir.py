# src/body/cli/commands/fix_ir.py
"""
IR (Incident Response) self-healing commands.

Provides:
- core-admin fix ir-triage
- core-admin fix ir-log

These commands bootstrap minimal IR artifacts under .intent/mind/ir
so that governance checks have something concrete to validate against.
"""

from __future__ import annotations

from pathlib import Path

import typer

from body.cli.commands.fix import (
    _confirm_dangerous_operation,
    _run_with_progress,
    console,
    fix_app,
    handle_command_errors,
)
from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)

IR_DIR = Path(settings.REPO_PATH) / ".intent" / "mind" / "ir"
TRIAGE_FILE = IR_DIR / "triage_log.yaml"
INCIDENT_LOG_FILE = IR_DIR / "incident_log.yaml"


def _ensure_ir_dir() -> None:
    """Ensure that the IR directory exists."""
    IR_DIR.mkdir(parents=True, exist_ok=True)


def _init_triage_log() -> None:
    """
    Initialize a minimal triage log file if it does not exist.

    The structure is intentionally simple. Future governance can evolve
    the schema; for now we only guarantee that the file exists and is
    a valid YAML-like structure.
    """
    _ensure_ir_dir()
    if TRIAGE_FILE.exists():
        logger.info("IR triage log already exists at %s", TRIAGE_FILE)
        return

    content = """\
version: "0.1.0"
type: "incident_triage_log"
entries: []
"""
    TRIAGE_FILE.write_text(content, encoding="utf-8")
    logger.info("Created IR triage log at %s", TRIAGE_FILE)


def _init_incident_log() -> None:
    """
    Initialize a minimal incident response log file if it does not exist.

    This is a placeholder structure to satisfy governance checks and
    provide a stable location for future IR entries.
    """
    _ensure_ir_dir()
    if INCIDENT_LOG_FILE.exists():
        logger.info("Incident log already exists at %s", INCIDENT_LOG_FILE)
        return

    content = """\
version: "0.1.0"
type: "incident_response_log"
entries: []
"""
    INCIDENT_LOG_FILE.write_text(content, encoding="utf-8")
    logger.info("Created incident log at %s", INCIDENT_LOG_FILE)


@fix_app.command("ir-triage", help="Initialize or update the incident triage log.")
@handle_command_errors
# ID: 620f3b9a-fd35-4c1e-95e3-5ea49887a92d
def fix_ir_triage(
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes to the IR triage log (creates file if missing).",
    ),
) -> None:
    """
    Bootstrap the IR triage log under .intent/mind/ir/.

    In the current implementation, this is idempotent and safe:
    - If the file exists, it is left unchanged.
    - If missing, a minimal skeleton is created.
    """
    if not _confirm_dangerous_operation("ir-triage", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    if not write:
        console.print(
            f"[yellow]Dry run:[/yellow] would ensure {TRIAGE_FILE} exists with a "
            "minimal triage log structure. Use --write to apply."
        )
        return

    _run_with_progress("Bootstrapping IR triage log", _init_triage_log)
    console.print(
        f"[green]✅ IR triage log ensured at[/green] [bold]{TRIAGE_FILE}[/bold]"
    )


@fix_app.command("ir-log", help="Initialize or update the incident response log.")
@handle_command_errors
# ID: a0eb79a8-e880-4f27-8233-aaa5f96ee9cb
def fix_ir_log(
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes to the IR incident log (creates file if missing).",
    ),
) -> None:
    """
    Bootstrap the main incident response log under .intent/mind/ir/.

    Same semantics as ir-triage:
    - Idempotent
    - Minimal structure only
    """
    if not _confirm_dangerous_operation("ir-log", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    if not write:
        console.print(
            f"[yellow]Dry run:[/yellow] would ensure {INCIDENT_LOG_FILE} exists "
            "with a minimal incident log structure. Use --write to apply."
        )
        return

    _run_with_progress("Bootstrapping IR incident log", _init_incident_log)
    console.print(
        f"[green]✅ IR incident log ensured at[/green] [bold]{INCIDENT_LOG_FILE}[/bold]"
    )
