#!/usr/bin/env python3
# scripts/verify_database_resource.py
"""
Verification script for database resource integration.

Tests:
1. Database resource is registered
2. All subcommands are available
3. Help text is present
4. Constitutional validation is enforced
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typer.testing import CliRunner
from rich.console import Console

console = Console()
runner = CliRunner()


def test_database_resource_registered():
    """Test that database resource is registered in main CLI."""
    from body.cli.admin_cli_v2 import app

    result = runner.invoke(app, ["--help"])

    if "database" not in result.stdout:
        console.print("[red]❌ Database resource not found in CLI[/red]")
        return False

    console.print("[green]✅ Database resource registered[/green]")
    return True


def test_database_subcommands():
    """Test that all database subcommands are available."""
    from body.cli.admin_cli_v2 import app

    result = runner.invoke(app, ["database", "--help"])

    expected_commands = ["sync", "migrate", "export", "cleanup", "status"]
    missing = []

    for cmd in expected_commands:
        if cmd not in result.stdout:
            missing.append(cmd)

    if missing:
        console.print(f"[red]❌ Missing commands: {', '.join(missing)}[/red]")
        return False

    console.print("[green]✅ All database subcommands present[/green]")
    return True


def test_help_text_quality():
    """Test that help text is informative."""
    from body.cli.admin_cli_v2 import app

    result = runner.invoke(app, ["database", "sync", "--help"])

    required_elements = [
        "Synchronize",  # Description
        "--write",      # Flag
        "Examples:",    # Usage examples
    ]

    missing = []
    for element in required_elements:
        if element not in result.stdout:
            missing.append(element)

    if missing:
        console.print(f"[red]❌ Help text missing: {', '.join(missing)}[/red]")
        return False

    console.print("[green]✅ Help text quality verified[/green]")
    return True


def test_constitutional_validation():
    """Test that validation framework is working."""
    from shared.cli_framework import validate_resource_name, ConstitutionalViolation

    # Test valid name
    try:
        validate_resource_name("database")
        console.print("[green]✅ Valid resource name accepted[/green]")
    except ConstitutionalViolation:
        console.print("[red]❌ Valid name rejected[/red]")
        return False

    # Test forbidden name
    try:
        validate_resource_name("body")
        console.print("[red]❌ Forbidden name not rejected[/red]")
        return False
    except ConstitutionalViolation:
        console.print("[green]✅ Forbidden name properly rejected[/green]")

    return True


def test_command_depth_validation():
    """Test command depth enforcement."""
    from shared.cli_framework import validate_command_depth, ConstitutionalViolation

    # Test valid depth
    try:
        validate_command_depth("database sync")
        console.print("[green]✅ Valid depth=2 accepted[/green]")
    except ConstitutionalViolation:
        console.print("[red]❌ Valid depth rejected[/red]")
        return False

    # Test invalid depth
    try:
        validate_command_depth("database foo bar")
        console.print("[red]❌ Invalid depth not rejected[/red]")
        return False
    except ConstitutionalViolation:
        console.print("[green]✅ Invalid depth properly rejected[/green]")

    return True


def main():
    """Run all verification tests."""
    console.print("\n[bold cyan]🔍 Database Resource Integration Verification[/bold cyan]\n")

    tests = [
        ("Registration", test_database_resource_registered),
        ("Subcommands", test_database_subcommands),
        ("Help Text", test_help_text_quality),
        ("Constitutional Validation", test_constitutional_validation),
        ("Command Depth", test_command_depth_validation),
    ]

    results = []
    for name, test_func in tests:
        console.print(f"\n[bold]Testing: {name}[/bold]")
        try:
            results.append(test_func())
        except Exception as e:
            console.print(f"[red]❌ Test failed with error: {e}[/red]")
            results.append(False)

    console.print("\n" + "="*60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        console.print(f"[bold green]✅ All tests passed ({passed}/{total})[/bold green]")
        return 0
    else:
        console.print(f"[bold red]❌ Some tests failed ({passed}/{total})[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
