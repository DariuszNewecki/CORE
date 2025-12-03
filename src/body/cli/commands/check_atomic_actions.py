# src/body/cli/commands/check_atomic_actions.py

"""
Constitutional checker for atomic actions pattern compliance.

This command validates that all atomic actions in CORE follow the universal
contract defined in .intent/charter/patterns/atomic_actions.yaml

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from shared.cli_utils import core_command
from shared.logger import getLogger

logger = getLogger(__name__)

atomic_actions_group = typer.Typer(
    help="Check atomic actions pattern compliance.", no_args_is_help=True
)


@atomic_actions_group.command("check")
@core_command(dangerous=False, requires_context=False)
# ID: 323b818b-d231-48d0-91f3-9589521c9dfb
def check_atomic_actions_cmd(
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
    from body.cli.logic.atomic_actions_checker import (
        AtomicActionsChecker,
        format_atomic_action_violations,
    )

    repo_root = Path.cwd()
    checker = AtomicActionsChecker(repo_root)

    if not quiet:
        typer.echo("🔍 Checking atomic actions pattern compliance...")

    # Run checks
    result = checker.check_all()

    # Handle output
    if output_json:
        output = {
            "total_actions": result.total_actions,
            "compliant_actions": result.compliant_actions,
            "compliance_rate": result.compliance_rate,
            "violations": [
                {
                    "file": str(v.file_path),
                    "function": v.function_name,
                    "rule": v.rule_id,
                    "message": v.message,
                    "severity": v.severity,
                    "line": v.line_number,
                    "suggested_fix": v.suggested_fix,
                }
                for v in result.violations
            ],
        }
        typer.echo(json.dumps(output, indent=2))

    elif not quiet:
        # Human-readable output
        typer.echo(format_atomic_action_violations(result.violations, verbose=verbose))

        if result.violations:
            error_count = len([v for v in result.violations if v.severity == "error"])
            warning_count = len(
                [v for v in result.violations if v.severity == "warning"]
            )

            typer.echo(f"\n📊 Atomic Actions Compliance: {result.compliance_rate:.1f}%")
            typer.echo(f"   Total actions: {result.total_actions}")
            typer.echo(f"   Compliant: {result.compliant_actions}")
            typer.echo(f"   Errors: {error_count}")
            typer.echo(f"   Warnings: {warning_count}")

            typer.echo("\n💡 Tip: All actions should follow the atomic_actions pattern")

    # Determine exit code
    has_errors = any(v.severity == "error" for v in result.violations)
    has_warnings = any(v.severity == "warning" for v in result.violations)

    if has_errors:
        raise typer.Exit(code=1)
    elif has_warnings:
        raise typer.Exit(code=2)
    else:
        if not quiet:
            typer.echo("\n✅ All atomic actions follow constitutional pattern!")
        raise typer.Exit(code=0)


@atomic_actions_group.command("list")
@core_command(dangerous=False, requires_context=False)
# ID: 85bf0824-6d3a-47a4-a464-a67eedf4a52f
def list_atomic_actions_cmd(
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
    from body.cli.logic.atomic_actions_checker import AtomicActionsChecker

    repo_root = Path.cwd()
    checker = AtomicActionsChecker(repo_root)

    typer.echo("🔍 Discovering atomic actions...\n")

    result = checker.check_all()

    # Get unique functions from violations and checks
    actions_map: dict[str, dict] = {}

    # This is a simplified version - in full implementation,
    # we'd track all discovered actions, not just violations
    for v in result.violations:
        key = f"{v.file_path}::{v.function_name}"
        if key not in actions_map:
            actions_map[key] = {
                "file": v.file_path,
                "function": v.function_name,
                "compliant": v.severity != "error",
            }

    typer.echo(f"📋 Found {result.total_actions} atomic actions\n")

    for key, info in sorted(actions_map.items()):
        status = "✅" if info["compliant"] else "❌"
        typer.echo(f"{status} {info['function']}")
        if show_details:
            rel_path = (
                info["file"].relative_to(Path.cwd())
                if Path.cwd() in info["file"].parents
                else info["file"]
            )
            typer.echo(f"   File: {rel_path}")
