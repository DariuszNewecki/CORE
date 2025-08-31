# src/system/admin/system.py
"""
Registers and implements the 'system' command group for the CORE Admin CLI.
This group contains commands related to developer lifecycle and system health,
such as running checks, tests, and formatters.
"""

from __future__ import annotations

import shutil
import subprocess

import typer

from shared.logger import getLogger

log = getLogger("core_admin.system")

system_app = typer.Typer(
    help="Commands for system health, testing, and developer workflows."
)

# --- THIS IS THE CRITICAL CHANGE ---
# The logic now lives here, not in the Makefile.
POETRY_EXECUTABLE = shutil.which("poetry")
LINT_PATHS = ["src", "tests"]


def _run_poetry_command(description: str, command: list[str]):
    """Helper to run a command via Poetry, log it, and handle errors."""
    if not POETRY_EXECUTABLE:
        log.error("❌ Could not find 'poetry' executable in your PATH.")
        raise typer.Exit(code=1)

    typer.secho(f"\n{description}", bold=True)
    full_command = [POETRY_EXECUTABLE, "run", *command]
    try:
        # We don't capture output, allowing the command to print directly to the console.
        subprocess.run(full_command, check=True, text=True)
    except subprocess.CalledProcessError:
        log.error(f"\n❌ Command failed: {' '.join(full_command)}")
        raise typer.Exit(code=1)


@system_app.command()
def lint():
    """Check code formatting and quality with Black and Ruff."""
    _run_poetry_command(
        "🎨 Checking code style with Black...",
        ["black", "--check", *LINT_PATHS],
    )
    _run_poetry_command(
        "🎨 Checking code quality with Ruff...",
        ["ruff", "check", *LINT_PATHS],
    )


@system_app.command(name="format")
def format_code():
    """Auto-format all code to be constitutionally compliant."""
    _run_poetry_command(
        "✨ Formatting code with Black...",
        ["black", *LINT_PATHS],
    )
    _run_poetry_command(
        "✨ Fixing code with Ruff...",
        ["ruff", "check", *LINT_PATHS, "--fix"],
    )


@system_app.command(name="test")
def test_system():
    """Run the pytest suite."""
    _run_poetry_command(
        "🧪 Running tests with pytest...",
        ["pytest"],
    )


@system_app.command()
def audit():
    """Run the full constitutional self-audit."""
    _run_poetry_command(
        "🧠 Running constitutional self-audit...",
        ["python", "-m", "src.core.capabilities"],
    )


@system_app.command()
def check():
    """Run all checks: lint, test, and a full constitutional audit."""
    typer.secho("🚀 Running all system checks...", fg=typer.colors.BLUE)
    try:
        lint()
        test_system()
        audit()
    except typer.Exit:
        # The subcommand will have already logged the error.
        raise typer.Exit(code=1)

    typer.secho("\n✅ All system checks passed successfully!", fg=typer.colors.GREEN)


def register(app: typer.Typer) -> None:
    """Register the 'system' command group with the main CLI app."""
    app.add_typer(system_app, name="system")
