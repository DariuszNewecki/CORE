# src/services/context/cli.py
"""
Context CLI commands for building, validating, and managing context packets.

Constitutional compliance: data_governance, operations
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from services.context import (
    ContextSerializer,
    ContextValidator,
)
from shared.cli_utils import display_error, display_info, display_success

console = Console()
app = typer.Typer(
    name="context",
    help="Context packet operations for governed LLM interactions",
    no_args_is_help=True,
)


# ID: cli.context.build
@app.command("build")
# ID: caac6251-83ec-4b0e-8915-c9921f88c0ed
def build_cmd(
    task: str = typer.Option(..., "--task", help="Task ID to build context for"),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Output path (default: work/context_packets/<task_id>/context.yaml)",
    ),
) -> None:
    """
    Build a context packet for a given task.

    Creates a validated, redacted context packet suitable for LLM consumption.
    """
    asyncio.run(_build_internal(task, out))


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
    asyncio.run(_show_internal(task))


async def _build_internal(task: str, out: Path | None) -> None:
    """Internal async implementation of build command."""
    try:
        display_info(f"Building context packet for task: {task}")

        # TODO: Wire up actual builder initialization with DB/Qdrant/AST providers
        # For now, this is a stub showing the intended flow

        # builder = ContextBuilder(db, qdrant, ast_provider, config)
        # packet = await builder.build_for_task(task_spec)
        # validator = ContextValidator()
        # is_valid, errors = validator.validate(packet)
        # if not is_valid:
        #     display_error(f"Validation failed: {errors}")
        #     raise typer.Exit(1)
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
        raise typer.Exit(1)

    except Exception as e:
        display_error(f"Failed to build context: {e}")
        raise typer.Exit(1)


def _validate_internal(file: Path) -> None:
    """Internal implementation of validate command."""
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


async def _show_internal(task: str) -> None:
    """Internal async implementation of show command."""
    try:
        display_info(f"Showing context packet metadata for task: {task}")

        # Placeholder: when ContextService wiring is complete, this will fetch from DB / disk.
        display_error(
            "Context 'show' command is not yet wired to ContextService. "
            "This is a structural placeholder."
        )
        raise typer.Exit(1)
    except Exception as e:
        display_error(f"Failed to show context: {e}")
        raise typer.Exit(1)
