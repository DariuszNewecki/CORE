# src/services/context/cli.py
"""
CLI commands for ContextPackage management.

Provides commands to build, validate, and inspect context packets
for LLM consumption with constitutional governance.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import typer
from rich.table import Table
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import console, display_error, display_info, display_success

from services.context import ContextSerializer, ContextValidator

app = typer.Typer(
    name="context",
    help="Manage ContextPackages for LLM consumption",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# CLI Commands (sync wrappers)
# ---------------------------------------------------------------------------


# ID: cli.context.build
@app.command("build")
# ID: 46c0e5a6-9c6e-4e22-a8c5-2a99ee6c7e0d
def build_cmd(
    task: str = typer.Option(..., "--task", help="Task ID to build context for"),
    out: Path | None = typer.Option(None, "--out", help="Output file path (optional)"),
) -> None:
    """
    Build a context packet for a given task.

    Creates a validated, redacted context packet suitable for LLM consumption.
    """
    result = asyncio.run(_build_internal(task, out))
    if not result.ok:
        raise typer.Exit(code=1)


# ID: cli.context.validate
@app.command("validate")
# ID: 63198399-73de-4460-a522-ce13a0a2e6cf
def validate_cmd(
    file: Path = typer.Option(
        ..., "--file", exists=True, help="Path to context packet YAML"
    ),
) -> None:
    """
    Validate a context packet against schema.

    Checks structural validity and constitutional compliance.
    """
    _validate_internal(file)


# ID: cli.context.show
@app.command("show")
# ID: 46218ce5-1c51-406b-9492-fb7caf5c3ed2
def show_cmd(
    task: str = typer.Option(..., "--task", help="Task ID to show context for"),
) -> None:
    """
    Show metadata for a context packet.

    Displays packet summary without revealing sensitive content.
    """
    result = asyncio.run(_show_internal(task))
    if not result.ok:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Internal Async Implementations (atomic actions)
# ---------------------------------------------------------------------------


@atomic_action(
    action_id="context.build",
    intent="Build a governed context packet for LLM consumption",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions", "data_governance"],
    category="context",
)
# ID: 91
async def _build_internal(task: str, out: Path | None) -> ActionResult:
    """
    Build a context packet for a given task.

    Args:
        task: Task identifier
        out: Optional output file path

    Returns:
        ActionResult with build status and packet location
    """
    start_time = time.time()

    try:
        display_info(f"Building context packet for task: {task}")

        # TODO: Wire up actual builder initialization with DB/Qdrant/AST providers
        # For now, this is a stub showing the intended flow

        # Placeholder implementation showing architectural intent:
        # builder = ContextBuilder(db, qdrant, ast_provider, config)
        # packet = await builder.build_for_task(task_spec)
        # validator = ContextValidator()
        # is_valid, errors = validator.validate(packet)
        # if not is_valid:
        #     return ActionResult(
        #         action_id="context.build",
        #         ok=False,
        #         data={"task": task, "errors": errors},
        #         duration_sec=time.time() - start_time,
        #         impact=ActionImpact.READ_ONLY,
        #         warnings=errors,
        #     )
        # redactor = ContextRedactor()
        # packet = redactor.redact(packet)
        # serializer = ContextSerializer()
        # output_path = out or Path(f"work/context_packets/{task}/context.yaml")
        # output_path.parent.mkdir(parents=True, exist_ok=True)
        # serializer.save(packet, output_path)

        display_error("ContextPackage build not yet fully implemented")
        display_info(
            "Run 'poetry run pytest tests/services/context/' to see current status"
        )

        return ActionResult(
            action_id="context.build",
            ok=False,
            data={
                "task": task,
                "status": "not_implemented",
                "output_path": str(out) if out else None,
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
            warnings=["ContextPackage build feature is under development"],
            suggestions=[
                "Run 'poetry run pytest tests/services/context/' for implementation status",
                "Check .intent/charter/patterns/ for ContextPackage architecture",
            ],
        )

    except Exception as e:
        display_error(f"Failed to build context: {e}")
        return ActionResult(
            action_id="context.build",
            ok=False,
            data={
                "task": task,
                "error": str(e),
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
            warnings=[f"Build failed: {e}"],
        )


def _validate_internal(file: Path) -> None:
    """
    Validate a context packet against schema.

    This is a sync helper for the CLI command.
    Does not return ActionResult as it's a validation display function.
    """
    try:
        display_info(f"Validating context packet: {file}")

        serializer = ContextSerializer()
        packet = serializer.from_yaml(str(file))

        validator = ContextValidator()
        is_valid, errors = validator.validate(packet)

        if is_valid:
            display_success("✓ Context packet is valid")

            # Show summary
            table = Table(title="Packet Summary")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")

            header = packet.get("header", {})
            table.add_row("Packet ID", header.get("packet_id", "N/A"))
            table.add_row("Task ID", header.get("task_id", "N/A"))
            table.add_row("Task Type", header.get("task_type", "N/A"))
            table.add_row("Privacy", header.get("privacy", "N/A"))

            context_items = len(packet.get("context", []))
            table.add_row("Context Items", str(context_items))

            console.print(table)
        else:
            display_error("✗ Context packet validation failed:")
            for error in errors:
                console.print(f"  - {error}", style="red")
            raise typer.Exit(1)
    except Exception as e:
        display_error(f"Error during validation: {e}")
        raise typer.Exit(1)


@atomic_action(
    action_id="context.show",
    intent="Display metadata for a context packet",
    impact=ActionImpact.READ_ONLY,
    policies=["atomic_actions", "data_governance"],
    category="context",
)
# ID: 169
async def _show_internal(task: str) -> ActionResult:
    """
    Show metadata for a context packet.

    Args:
        task: Task identifier

    Returns:
        ActionResult with packet metadata
    """
    start_time = time.time()

    try:
        display_info(f"Showing context packet metadata for task: {task}")

        # Placeholder: when ContextService wiring is complete, this will fetch from DB / disk.
        # Architectural intent:
        # context_service = get_context_service()
        # packet_metadata = await context_service.get_packet_metadata(task)
        #
        # if packet_metadata:
        #     return ActionResult(
        #         action_id="context.show",
        #         ok=True,
        #         data={
        #             "task": task,
        #             "packet_id": packet_metadata.packet_id,
        #             "created_at": packet_metadata.created_at,
        #             "size_tokens": packet_metadata.size_tokens,
        #             "context_items": packet_metadata.context_items,
        #         },
        #         duration_sec=time.time() - start_time,
        #         impact=ActionImpact.READ_ONLY,
        #     )

        display_error(
            "Context 'show' command is not yet wired to ContextService. "
            "This is a structural placeholder."
        )

        return ActionResult(
            action_id="context.show",
            ok=False,
            data={
                "task": task,
                "status": "not_implemented",
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
            warnings=["ContextService wiring is under development"],
            suggestions=[
                "Check services/context/ for implementation progress",
                "Review ContextDatabase and ContextCache classes for metadata storage",
            ],
        )

    except Exception as e:
        display_error(f"Failed to show context: {e}")
        return ActionResult(
            action_id="context.show",
            ok=False,
            data={
                "task": task,
                "error": str(e),
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
            warnings=[f"Show failed: {e}"],
        )
