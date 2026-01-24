# src/body/cli/commands/check_patterns.py

"""
Pattern compliance checking commands.
Validates code against design patterns defined in .intent/charter/patterns/

MODERNIZED (V2): This command is now a thin shell that delegates analysis
to the PatternEvaluator component.

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import json

import typer

from body.evaluators.pattern_evaluator import (
    PatternEvaluator,
    format_violations,
    load_patterns_dict,
)
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models.pattern_graph import PatternViolation


logger = getLogger(__name__)

patterns_group = typer.Typer(
    help="Check and validate design pattern compliance.", no_args_is_help=True
)


@patterns_group.command("list")
@core_command(dangerous=False, requires_context=True)
# ID: 81a81ff1-429a-48c1-9d96-53c2858be50d
async def list_patterns(
    ctx: typer.Context,
    category: str = typer.Option(
        None,
        "--category",
        help="Filter by category (commands, services, agents, workflows)",
    ),
):
    """
    List available design patterns.
    """
    # Load patterns directly using helper function
    core_context: CoreContext = ctx.obj
    repo_root = core_context.git_service.repo_path
    patterns = load_patterns_dict(repo_root)

    typer.echo("📋 Available Design Patterns:\n")

    for pattern_category, pattern_spec in patterns.items():
        if category and pattern_category != category:
            continue

        typer.echo(f"Category: {pattern_spec.get('title', pattern_category)}")
        typer.echo(f"  Version: {pattern_spec.get('version', 'unknown')}")
        typer.echo(f"  File: {pattern_category}_patterns.yaml\n")

        for pattern in pattern_spec.get("patterns", []):
            typer.echo(f"  • {pattern['pattern_id']}")
            typer.echo(f"    Type: {pattern.get('type', 'unknown')}")
            typer.echo(f"    Purpose: {pattern.get('purpose', 'none')}")
            typer.echo()


@patterns_group.command("check")
@core_command(dangerous=False, requires_context=True)
# ID: 93383a52-2beb-46ff-9ade-0b9da94ce51e
async def check_patterns_cmd(
    ctx: typer.Context,
    category: str = typer.Option(
        "all",
        "--category",
        help="Category to check (commands, services, agents, workflows, all)",
    ),
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
    Check code compliance with design patterns via the PatternEvaluator.
    """
    if not quiet:
        typer.echo(f"🔍 [V2] Checking {category} pattern compliance...")

    # EXECUTE EVALUATOR (Body Layer)
    core_context: CoreContext = ctx.obj
    evaluator = PatternEvaluator()
    result_wrapper = await evaluator.execute(
        category=category, repo_root=core_context.git_service.repo_path
    )
    data = result_wrapper.data

    # Handle output
    if output_json:
        typer.echo(json.dumps(data, indent=2))

    elif not quiet:
        # Reconstruct models for the UI formatter
        violations = [
            PatternViolation(
                file_path=v["file"],
                component_name=v["component"],
                pattern_id=v["pattern"],
                violation_type=v["type"],
                message=v["message"],
                severity=v["severity"],
                line_number=v["line"],
            )
            for v in data["violations"]
        ]

        # Human-readable output
        typer.echo(format_violations(violations, verbose=verbose))

        if violations:
            error_count = len([v for v in violations if v.severity == "error"])
            warning_count = len([v for v in violations if v.severity == "warning"])

            typer.echo(f"\n📊 Pattern Compliance: {data['compliance_rate']:.1f}%")
            typer.echo(f"   Total components: {data['total']}")
            typer.echo(f"   Compliant: {data['compliant']}")
            typer.echo(f"   Errors: {error_count}")
            typer.echo(f"   Warnings: {warning_count}")

            typer.echo(
                "\n💡 Tip: Run 'core-admin fix patterns --write' to auto-fix some violations"
            )

    # Determine exit code based on ComponentResult status
    if not result_wrapper.ok:
        has_errors = any(v["severity"] == "error" for v in data["violations"])
        raise typer.Exit(code=1 if has_errors else 2)
    else:
        if not quiet:
            typer.echo("\n✅ All pattern checks passed!")
        raise typer.Exit(code=0)
