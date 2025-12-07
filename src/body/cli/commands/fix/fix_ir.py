# src/body/cli/commands/fix/fix_ir.py
"""
IR (Incident Response) self-healing commands.

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

from pathlib import Path

import typer

from body.cli.commands.fix import (
    console,
    fix_app,
    handle_command_errors,
)
from shared.cli_utils import core_command
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)

IR_DIR = Path(settings.REPO_PATH) / ".intent" / "mind" / "ir"
TRIAGE_FILE = IR_DIR / "triage_log.yaml"
INCIDENT_LOG_FILE = IR_DIR / "incident_log.yaml"

TRIAGE_CONTENT = """\
version: "0.1.0"
type: "incident_triage_log"
entries: []
"""

INCIDENT_LOG_CONTENT = """\
version: "0.1.0"
type: "incident_response_log"
entries: []
"""


def _ensure_ir_file(path: Path, content: str, label: str) -> None:
    """
    Helper: Ensure a minimal IR artifact exists.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        logger.info("%s already exists at %s", label, path)
        console.print("[yellow]ℹ %s already exists.[/yellow]", label)
        return

    path.write_text(content, encoding="utf-8")
    logger.info("Created %s at %s", label, path)
    console.print("[green]✅ Created %s[/green]", label)


def _run_ir_fix(path: Path, content: str, label: str, write: bool) -> None:
    """
    Generic handler for IR fix commands.
    """
    # Safety check handled by @core_command decorator

    if not write:
        console.print(
            f"[yellow]Dry run:[/yellow] would ensure {path} exists with a "
            f"minimal {label.lower()} structure. Use --write to apply."
        )
        return

    _ensure_ir_file(path, content, label)


@fix_app.command("ir-triage", help="Initialize or update the incident triage log.")
@handle_command_errors
@core_command(dangerous=True, confirmation=False)
# ID: cfce8395-9fdd-420e-bbaf-4cc18723bd5c
def fix_ir_triage(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes to the IR triage log (creates file if missing).",
    ),
) -> None:
    """
    Bootstrap the IR triage log under .intent/mind/ir/.
    """
    _run_ir_fix(TRIAGE_FILE, TRIAGE_CONTENT, "IR triage log", write)


@fix_app.command("ir-log", help="Initialize or update the incident response log.")
@handle_command_errors
@core_command(dangerous=True, confirmation=False)
# ID: c3e0e9ae-2e2e-4c7f-ac49-a857d44bfb86
def fix_ir_log(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes to the IR incident log (creates file if missing).",
    ),
) -> None:
    """
    Bootstrap the main incident response log under .intent/mind/ir/.
    """
    _run_ir_fix(INCIDENT_LOG_FILE, INCIDENT_LOG_CONTENT, "IR incident log", write)
