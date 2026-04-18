# src/cli/commands/fix/fix_ir.py
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

from cli.utils import core_command
from shared.logger import getLogger

from . import fix_app


if TYPE_CHECKING:
    from shared.context import CoreContext
logger = getLogger(__name__)
IR_DIR = Path(".intent") / "mind" / "ir"
TRIAGE_FILE = IR_DIR / "triage_log.yaml"
INCIDENT_LOG_FILE = IR_DIR / "incident_log.yaml"
TRIAGE_CONTENT = 'version: "0.1.0"\ntype: "incident_triage_log"\nentries: []\n'
INCIDENT_LOG_CONTENT = 'version: "0.1.0"\ntype: "incident_response_log"\nentries: []\n'


def _run_ir_fix(
    context: CoreContext, path: Path, content: str, label: str, write: bool
) -> None:
    """
    Generic handler for IR fix commands using the governed FileHandler.
    """
    rel_path = str(path).replace("\\", "/")
    if not write:
        logger.info(
            "[yellow]Dry run:[/yellow] would ensure %s exists with a minimal %s structure. Use --write to apply.",
            rel_path,
            label.lower(),
        )
        return
    try:
        context.file_handler.write_runtime_text(rel_path, content)
        logger.info("Governed Write: %s at %s", label, rel_path)
        logger.info("[green]✅ Created %s[/green]", label)
    except Exception as e:
        logger.error("Failed to bootstrap %s: %s", label, e)
        logger.info("[red]❌ Failed to create %s: %s[/red]", label, e)


@fix_app.command("ir-triage", help="Initialize or update the incident triage log.")
@core_command(dangerous=True, confirmation=False)
# ID: c50add43-9412-44ad-b261-6f64aed07b21
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
# ID: e2f34a52-0839-4146-bafd-7ce6b559a510
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
