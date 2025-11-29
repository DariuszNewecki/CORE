# src/body/cli/commands/check_patterns.py

"""
Pattern compliance checking commands.
Validates code against design patterns defined in .intent/charter/patterns/
"""

from __future__ import annotations

from pathlib import Path

import typer
from shared.logger import getLogger

logger = getLogger(__name__)

patterns_group = typer.Typer(
    help="Check and validate design pattern compliance.", no_args_is_help=True
)


@patterns_group.command("list")
# ID: 80fc8e42-3f81-4448-9705-e5b412292a89
def list_patterns(
    category: str = typer.Option(
        None,
        "--category",
        help="Filter by category (commands, services, agents, workflows)",
    ),
):
    """
    List available design patterns.

    Shows all patterns defined in .intent/charter/patterns/
    """
    try:
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

    except Exception as e:
        logger.error(f"Failed to list patterns: {e}")
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(code=1)


@patterns_group.command("check")
# ID: fa3bc962-0c48-4708-b0a2-d1e4b7bfe160
def check_patterns_cmd(
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

    Validates that all code follows the patterns defined in
    .intent/charter/patterns/*.yaml

    Exit codes:
        0: All checks passed
        1: Violations found
        2: Warnings only (no errors)
    """
    try:
        from body.cli.logic.pattern_checker import PatternChecker, format_violations

        repo_root = Path.cwd()
        checker = PatternChecker(repo_root)

        if not quiet:
            typer.echo("🔍 Checking pattern compliance...")

        # Run checks
        if category == "all":
            result = checker.check_all()
        else:
            violations = checker.check_category(category)
            # Would need to construct result object - for now just check all
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
                error_count = len(
                    [v for v in result.violations if v.severity == "error"]
                )
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

    except typer.Exit:
        raise
    except Exception as e:
        logger.error(f"Pattern check failed: {e}")
        if not quiet:
            typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(code=1)


@patterns_group.command("show")
# ID: 6fc76beb-dfe5-4aad-9aa9-ceaa3a904280
def show_pattern(
    pattern_id: str = typer.Argument(
        ..., help="Pattern identifier (e.g., 'inspect_pattern')"
    ),
):
    """
    Show detailed information about a specific pattern.
    """
    try:
        from body.cli.logic.pattern_checker import PatternChecker

        repo_root = Path.cwd()
        checker = PatternChecker(repo_root)

        # Find pattern
        for pattern_spec in checker.patterns.values():
            for pattern in pattern_spec.get("patterns", []):
                if pattern["pattern_id"] == pattern_id:
                    typer.echo(f"\n📘 Pattern: {pattern['pattern_id']}\n")
                    typer.echo(f"Type: {pattern.get('type', 'unknown')}")
                    typer.echo(f"Purpose: {pattern.get('purpose', 'N/A')}\n")

                    if "applies_to" in pattern:
                        typer.echo("Applies to:")
                        for item in pattern["applies_to"]:
                            typer.echo(f"  • {item}")
                        typer.echo()

                    if "guarantees" in pattern:
                        typer.echo("Guarantees:")
                        for guarantee in pattern["guarantees"]:
                            typer.echo(f"  • {guarantee}")
                        typer.echo()

                    if "implementation_requirements" in pattern:
                        typer.echo("Implementation Requirements:")
                        reqs = pattern["implementation_requirements"]
                        if isinstance(reqs, dict):
                            for key, value in reqs.items():
                                typer.echo(f"  {key}:")
                                if isinstance(value, list):
                                    for item in value:
                                        typer.echo(f"    • {item}")
                                else:
                                    typer.echo(f"    {value}")
                        typer.echo()

                    return

        typer.echo(f"❌ Pattern '{pattern_id}' not found")
        raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        logger.error(f"Failed to show pattern: {e}")
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(code=1)
