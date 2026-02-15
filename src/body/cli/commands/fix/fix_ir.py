# src/body/cli/commands/fix/fix_ir.py
# ID: 6cfe3b4a-f3bf-4fa9-8639-1676fb212e39
"""
IR (Incident Response) self-healing commands.

Refactored to use the Constitutional CLI Framework (@core_command).
CONSTITUTIONAL FIX: All mutations now route through FileHandler to ensure
IntentGuard enforcement and auditability.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from shared.cli_utils import core_command
from shared.logger import getLogger

# We only import the App and Console from the local hub
from . import (
    console,
    fix_app,
)


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

IR_DIR = Path(".intent") / "mind" / "ir"
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


def _run_ir_fix(
    context: CoreContext, path: Path, content: str, label: str, write: bool
) -> None:
    """
    Generic handler for IR fix commands using the governed FileHandler.
    """
    rel_path = str(path).replace("\\", "/")

    if not write:
        console.print(
            f"[yellow]Dry run:[/yellow] would ensure {rel_path} exists with a "
            f"minimal {label.lower()} structure. Use --write to apply."
        )
        return

    try:
        context.file_handler.write_runtime_text(rel_path, content)
        logger.info("Governed Write: %s at %s", label, rel_path)
        console.print(f"[green]✅ Created {label}[/green]")
    except Exception as e:
        logger.error("Failed to bootstrap %s: %s", label, e)
        console.print(f"[red]❌ Failed to create {label}: {e}[/red]")


@fix_app.command("ir-triage", help="Initialize or update the incident triage log.")
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
    core_context: CoreContext = ctx.obj
    _run_ir_fix(core_context, TRIAGE_FILE, TRIAGE_CONTENT, "IR triage log", write)


@fix_app.command("ir-log", help="Initialize or update the incident response log.")
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
    core_context: CoreContext = ctx.obj
    _run_ir_fix(
        core_context, INCIDENT_LOG_FILE, INCIDENT_LOG_CONTENT, "IR incident log", write
    )
