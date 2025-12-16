# src/body/cli/commands/manage/emergency.py
# ID: cli.manage.emergency
"""
Emergency Override Protocols ("Break Glass").
Allows bypassing IntentGuard in critical failure scenarios.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer

from shared.cli_utils import core_command
from shared.infrastructure.events.base import CloudEvent
from shared.infrastructure.events.bus import EventBus
from shared.logger import getLogger


logger = getLogger(__name__)
app = typer.Typer()

# This file indicates the system is in Emergency Mode
EMERGENCY_LOCK_FILE = Path(".intent/mind/.emergency_override")


@core_command(dangerous=True)
@app.command("break-glass")
# ID: 5d1ddd03-7493-42f7-84a3-97238c77f7f3
def break_glass(
    reason: Annotated[
        str, typer.Option("--reason", help="Incident ticket or critical reason")
    ],
) -> None:
    """
    CRITICAL: Activates Emergency Override Mode.
    Bypasses IntentGuard validation. Logs CRITICAL audit event.
    Requires CORE_EMERGENCY_TOKEN env var to be set.
    """
    token = os.environ.get("CORE_EMERGENCY_TOKEN")
    if not token:
        logger.critical("Attempted break-glass without CORE_EMERGENCY_TOKEN")
        typer.echo(
            "❌ Error: CORE_EMERGENCY_TOKEN environment variable not set.", err=True
        )
        raise typer.Exit(code=1)

    logger.critical("BREAK GLASS PROTOCOL INITIATED. Reason: %s", reason)

    try:
        # 1. Write the lockfile
        EMERGENCY_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        EMERGENCY_LOCK_FILE.write_text(f"active|{reason}")

        # 2. Emit Critical Event
        bus = EventBus.get_instance()
        event = CloudEvent(
            type="core.governance.emergency_override",
            source="cli:manage.emergency",
            data={
                "reason": reason,
                "user": os.environ.get("USER", "unknown"),
                "action": "activate",
            },
        )
        bus.emit(event)

        # 3. User Feedback
        typer.echo("\n🚨 EMERGENCY OVERRIDE ACTIVE. INTENT GUARD DISABLED. 🚨")
        typer.echo("System is now in Post-Mortem Lockdown.")
        typer.echo("Only manual CLI commands should be executed until resolution.\n")

    except Exception as e:
        logger.exception("Failed to activate emergency mode")
        typer.echo(f"❌ Critical failure activating emergency mode: {e}", err=True)
        raise typer.Exit(code=1)


@core_command(dangerous=True)
@app.command("resume")
# ID: 4e24a0e9-37b1-4891-9474-af01ea6a4b53
def resume() -> None:
    """
    Deactivates Emergency Override Mode.
    Should be run after system integrity is verified.
    """
    if EMERGENCY_LOCK_FILE.exists():
        try:
            EMERGENCY_LOCK_FILE.unlink()

            # Emit Event
            bus = EventBus.get_instance()
            event = CloudEvent(
                type="core.governance.emergency_override",
                source="cli:manage.emergency",
                data={
                    "user": os.environ.get("USER", "unknown"),
                    "action": "deactivate",
                },
            )
            bus.emit(event)

            logger.info("Emergency override cleared. Intent Guard re-engaged.")
            typer.echo("✅ Emergency override cleared. Intent Guard re-engaged.")
        except Exception as e:
            logger.exception("Failed to deactivate emergency mode")
            typer.echo(f"❌ Error removing lock file: {e}", err=True)
            raise typer.Exit(code=1)
    else:
        logger.warning("No emergency override was active.")
        typer.echo("ℹ️  No emergency override was active.")
