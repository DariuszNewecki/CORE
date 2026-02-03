# src/shared/infrastructure/context/cli.py

"""
CLI commands for ContextPackage management.

Provides commands to build, validate, and inspect context packets
for LLM consumption with constitutional governance.
"""

from __future__ import annotations

import time
from pathlib import Path

import typer

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.infrastructure.context import ContextSerializer, ContextValidator


app = typer.Typer(
    name="context",
    help="Manage ContextPackages for LLM consumption",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------


@app.command("build")
# ID: 46c0e5a6-9c6e-4e22-a8c5-2a99ee6c7e0d
async def build_cmd(
    task: str = typer.Option(..., "--task", help="Task ID to build context for"),
    out: Path | None = typer.Option(None, "--out", help="Output file path (optional)"),
) -> None:
    """
    Build a context packet for a given task.

    Creates a validated, redacted context packet suitable for LLM consumption.
    """
    result = await _build_internal(task, out)
    if not result.ok:
        raise typer.Exit(code=1)


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


@app.command("show")
# ID: 46218ce5-1c51-406b-9492-fb7caf5c3ed2
async def show_cmd(
    task: str = typer.Option(..., "--task", help="Task ID to show context for"),
) -> None:
    """
    Show metadata for a context packet.

    Displays packet summary without revealing sensitive content.
    """
    result = await _show_internal(task)
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
        # FUTURE: Wire up actual builder initialization with DB/Qdrant/AST providers
        # For now, this is a stub showing the intended flow
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
                "Check .intent/patterns/ for ContextPackage architecture",
            ],
        )

    except Exception as e:
        return ActionResult(
            action_id="context.build",
            ok=False,
            data={
                "task": task,
                "error": str(e),
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
            warnings=[f"Build failed: {e!s}"],
        )


def _validate_internal(file: Path) -> None:
    """
    Validate a context packet against schema.

    This is a sync helper for the CLI command.
    Does not return ActionResult as it's a validation display function.
    """
    serializer = ContextSerializer()
    packet = serializer.from_yaml(str(file))

    validator = ContextValidator()
    is_valid, _errors = validator.validate(packet)

    if not is_valid:
        raise typer.Exit(1)


@atomic_action(
    action_id="context.show",
    intent="Display metadata for a context packet",
    impact=ActionImpact.READ_ONLY,
    policies=["atomic_actions", "data_governance"],
    category="context",
)
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
        # Placeholder: when ContextService wiring is complete, this will fetch from DB / disk.
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
        return ActionResult(
            action_id="context.show",
            ok=False,
            data={
                "task": task,
                "error": str(e),
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
            warnings=[f"Show failed: {e!s}"],
        )
