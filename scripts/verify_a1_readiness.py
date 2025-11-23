# scripts/verify_a1_readiness.py
"""
A standalone script to clearly demonstrate the architectural gap preventing
A1 autonomy from functioning correctly. It provides evidence by comparing the
result of the correct validation command against the one currently being
used by the A1 executor's pre-flight check.
"""

import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

# --- Configuration ---
REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWN_GOOD_FILE = "src/shared/logger.py"

# The command that we know is correct and works
CORRECT_VALIDATION_COMMAND = [
    "poetry",
    "run",
    "core-admin",
    "check",
    "validate",
    KNOWN_GOOD_FILE,
]

# The command that the buggy `micro apply` script is currently trying to run
BUGGY_PREFLIGHT_COMMAND = [
    "poetry",
    "run",
    "core-admin",
    "validate",
    "code",
    KNOWN_GOOD_FILE,
]
# --- End Configuration ---


def run_command(command: list[str]) -> tuple[bool, str]:
    """Runs a command and returns (success_bool, combined_output_str)."""
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,  # We want to capture failures, not crash
        )
        output = result.stdout + "\n" + result.stderr
        return result.returncode == 0, output.strip()
    except FileNotFoundError:
        return False, f"Command not found: {command[0]}"


def main():
    """Main execution function for the verification script."""
    console.print(Panel("[bold cyan]CORE A1 Readiness Verification Script[/bold cyan]"))

    # --- TEST A: ESTABLISH GROUND TRUTH ---
    console.print("\n[bold]STEP 1: Verifying the canonical validation tool...[/bold]")
    console.print(
        f"  -> Running correct command: `{' '.join(CORRECT_VALIDATION_COMMAND)}`"
    )
    success_a, output_a = run_command(CORRECT_VALIDATION_COMMAND)

    if not success_a:
        console.print(
            "[bold red]❌ TEST FAILED: The baseline validation tool itself is broken.[/bold red]"
        )
        console.print("Output:")
        console.print(output_a)
        sys.exit(1)

    console.print(
        "[bold green]  -> ✅ SUCCESS: The canonical validation tool is healthy.[/bold green]"
    )
    console.print("     This proves the system *is capable* of validating a file.")

    # --- TEST B: SIMULATE THE BUGGY A1 PRE-FLIGHT CHECK ---
    console.print(
        "\n[bold]STEP 2: Simulating the A1 micro-proposal pre-flight check...[/bold]"
    )
    console.print(
        f"  -> Running the command currently used by `micro apply`: `{' '.join(BUGGY_PREFLIGHT_COMMAND)}`"
    )
    success_b, output_b = run_command(BUGGY_PREFLIGHT_COMMAND)

    console.print("\n" + "=" * 50)
    console.print("[bold]VERIFICATION ANALYSIS[/bold]")
    console.print("=" * 50)

    if success_b:
        console.print(
            "[bold red]UNEXPECTED RESULT:[/bold red] The buggy pre-flight check succeeded."
        )
        console.print(
            "This indicates a different problem than anticipated. Please review the output:"
        )
        console.print(output_b)
        sys.exit(1)

    if "No such command 'validate'" in output_b:
        console.print(
            "[bold green]✅ EVIDENCE CONFIRMED: The A1 pre-flight check is failing as expected.[/bold green]"
        )
        console.print("\n[bold]Conclusion:[/bold]")
        console.print(
            "The system is not yet in A1 because of a simple but critical architectural disconnect:"
        )
        console.print(
            "1. The **correct** validation command is `core-admin check validate` (as proven in Step 1)."
        )
        console.print(
            "2. The **A1 executor** is incorrectly trying to call `core-admin validate code` (as proven by the failure in Step 2)."
        )
        console.print(
            "\nThe A1 autonomy loop is correctly halting because its pre-flight check is calling a non-existent command."
        )
        console.print(
            "\nThis script provides the clear evidence that the final step is to fix this wiring."
        )
    else:
        console.print(
            "[bold yellow]UNEXPECTED FAILURE:[/bold yellow] The pre-flight check failed, but for a different reason."
        )
        console.print("Please review the captured output to diagnose the issue:")
        console.print(Panel(output_b, title="Captured Output from Buggy Command"))

    sys.exit(0)


if __name__ == "__main__":
    main()
