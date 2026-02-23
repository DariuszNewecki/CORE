# src/body/cli/commands/check_atomic_actions.py

"""
Constitutional checker for atomic actions pattern compliance.

MODERNIZED (V2): This command is now a thin shell that delegates analysis
to the AtomicActionsEvaluator component.

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from body.evaluators.atomic_actions_evaluator import (
    AtomicActionsEvaluator,
    AtomicActionViolation,
    format_atomic_action_violations,
)
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)

atomic_actions_group = typer.Typer(
    help="Check atomic actions pattern compliance.", no_args_is_help=True
)


@atomic_actions_group.command("check")
@core_command(dangerous=False, requires_context=True)
# ID: 323b818b-d231-48d0-91f3-9589521c9dfb
async def check_atomic_actions_cmd(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Show detailed violation information",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress output, exit code only",
    ),
):
    """
    Check atomic actions compliance with constitutional pattern.

    Validates that all atomic actions follow the universal contract:
    - Return ActionResult
    - Have @atomic_action decorator
    - Declare action_id, intent, impact, policies
    - Use structured data contracts
    """
    if not quiet:
        typer.echo("🔍 [V2] Checking atomic actions pattern compliance...")

    # EXECUTE EVALUATOR (The Mind/Body Logic)
    core_context: CoreContext = ctx.obj
    evaluator = AtomicActionsEvaluator()
    # Note: execute() returns a ComponentResult
    result_wrapper = await evaluator.execute(
        repo_root=core_context.git_service.repo_path
    )
    data = result_wrapper.data

    # Handle output
    if output_json:
        typer.echo(json.dumps(data, indent=2))

    elif not quiet:
        # Reconstruct violation objects for formatter
        violations = [
            AtomicActionViolation(
                file_path=Path(v["file"]),
                function_name=v["function"],
                rule_id=v["rule"],
                message=v["message"],
                severity=v["severity"],
                line_number=v["line"],
                suggested_fix=v["suggested_fix"],
            )
            for v in data["violations"]
        ]

        # Human-readable output
        typer.echo(format_atomic_action_violations(violations, verbose=verbose))

        if violations:
            error_count = len([v for v in violations if v.severity == "error"])
            warning_count = len([v for v in violations if v.severity == "warning"])

            typer.echo(
                f"\n📊 Atomic Actions Compliance: {data['compliance_rate']:.1f}%"
            )
            typer.echo(f"   Total actions: {data['total_actions']}")
            typer.echo(f"   Compliant: {data['compliant_actions']}")
            typer.echo(f"   Errors: {error_count}")
            typer.echo(f"   Warnings: {warning_count}")

            typer.echo("\n💡 Tip: All actions should follow the atomic_actions pattern")

    # Determine exit code based on the ComponentResult success status
    if not result_wrapper.ok:
        # Check if it was a hard error or just warnings
        has_errors = any(v["severity"] == "error" for v in data["violations"])
        raise typer.Exit(code=1 if has_errors else 2)
    else:
        if not quiet:
            typer.echo("\n✅ All atomic actions follow constitutional pattern!")
        raise typer.Exit(code=0)


@atomic_actions_group.command("list")
@core_command(dangerous=False, requires_context=True)
# ID: 85bf0824-6d3a-47a4-a464-a67eedf4a52f
async def list_atomic_actions_cmd(
    ctx: typer.Context,
    show_details: bool = typer.Option(
        False,
        "--details",
        help="Show detailed action metadata",
    ),
):
    """
    List all atomic actions discovered in the codebase.

    Shows which functions are identified as atomic actions and
    their compliance status.
    """
    typer.echo("🔍 Discovering atomic actions...\n")

    core_context: CoreContext = ctx.obj
    evaluator = AtomicActionsEvaluator()
    result_wrapper = await evaluator.execute(
        repo_root=core_context.git_service.repo_path
    )
    data = result_wrapper.data

    # Map discovered actions
    actions_map: dict[str, dict] = {}

    for v in data["violations"]:
        key = f"{v['file']}::{v['function']}"
        if key not in actions_map:
            actions_map[key] = {
                "file": v["file"],
                "function": v["function"],
                "compliant": v["severity"] != "error",
            }

    typer.echo(f"📋 Found {data['total_actions']} atomic actions\n")

    for key, info in sorted(actions_map.items()):
        status = "✅" if info["compliant"] else "❌"
        typer.echo(f"{status} {info['function']}")
        if show_details:
            typer.echo(f"   File: {info['file']}")
