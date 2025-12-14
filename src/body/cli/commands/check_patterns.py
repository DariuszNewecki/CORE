# src/body/cli/commands/check_patterns.py

"""
Pattern compliance checking commands.
Validates code against design patterns defined in .intent/charter/patterns/

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

from pathlib import Path

import typer

from shared.cli_utils import core_command
from shared.logger import getLogger


logger = getLogger(__name__)

patterns_group = typer.Typer(
    help="Check and validate design pattern compliance.", no_args_is_help=True
)


@patterns_group.command("list")
@core_command(dangerous=False, requires_context=False)
# ID: 81a81ff1-429a-48c1-9d96-53c2858be50d
def list_patterns(
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
    from body.cli.logic.pattern_checker import PatternChecker

    repo_root = Path.cwd()
    checker = PatternChecker(repo_root)

    typer.echo("📋 Available Design Patterns:\n")

    for pattern_category, pattern_spec in checker.patterns.items():
        if category and pattern_category != category:
            continue

        typer.echo(f"Category: {pattern_spec.get('title', pattern_category)}")
        typer.echo(f"  Version: {pattern_spec.get('version', 'unknown')}")
        typer.echo(f"  File: {pattern_category}_patterns.yaml\n")

        for pattern in pattern_spec.get("patterns", []):
            typer.echo(f"  • {pattern['pattern_id']}")
            typer.echo(f"    Type: {pattern.get('type', 'unknown')}")
            typer.echo(f"    Purpose: {pattern.get('purpose', 'N/A')}")
            typer.echo()


@patterns_group.command("check")
@core_command(dangerous=False, requires_context=False)
# ID: 93383a52-2beb-46ff-9ade-0b9da94ce51e
def check_patterns_cmd(
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
    Check code compliance with design patterns.
    """
    from body.cli.logic.pattern_checker import PatternChecker, format_violations

    repo_root = Path.cwd()
    checker = PatternChecker(repo_root)

    if not quiet:
        typer.echo("🔍 Checking pattern compliance...")

    # Run checks
    if category == "all":
        result = checker.check_all()
    else:
        # checker.check_category returns just violations list
        # We'd need to wrap this if we want full stats, but for now
        # defaulting to full check is safer for the tool's current contract.
        result = checker.check_all()

    # Handle output
    if output_json:
        import json

        output = {
            "total": result.total_components,
            "compliant": result.compliant,
            "compliance_rate": result.compliance_rate,
            "violations": [
                {
                    "file": str(v.file_path),
                    "component": v.component_name,
                    "pattern": v.expected_pattern,
                    "type": v.violation_type,
                    "message": v.message,
                    "severity": v.severity,
                    "line": v.line_number,
                }
                for v in result.violations
            ],
        }
        typer.echo(json.dumps(output, indent=2))

    elif not quiet:
        # Human-readable output
        typer.echo(format_violations(result.violations, verbose=verbose))

        if result.violations:
            error_count = len([v for v in result.violations if v.severity == "error"])
            warning_count = len(
                [v for v in result.violations if v.severity == "warning"]
            )

            typer.echo(f"\n📊 Pattern Compliance: {result.compliance_rate:.1f}%")
            typer.echo(f"   Total components: {result.total_components}")
            typer.echo(f"   Compliant: {result.compliant}")
            typer.echo(f"   Errors: {error_count}")
            typer.echo(f"   Warnings: {warning_count}")

            typer.echo(
                "\n💡 Tip: Run 'core-admin fix patterns --write' to auto-fix some violations"
            )

    # Determine exit code
    has_errors = any(v.severity == "error" for v in result.violations)
    has_warnings = any(v.severity == "warning" for v in result.violations)

    if has_errors:
        raise typer.Exit(code=1)
    elif has_warnings:
        raise typer.Exit(code=2)
    else:
        if not quiet:
            typer.echo("\n✅ All pattern checks passed!")
        raise typer.Exit(code=0)
