# scripts/diagnose_auditor_discovery.py
"""
A diagnostic script to test the importability of all constitutional checks
and pinpoint the exact module that is breaking the auditor's discovery loop.
"""
import importlib
import pkgutil
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel  # <-- THIS IS THE FIX

console = Console()

# Add the 'src' directory to the Python path to allow imports
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# The target package we want to inspect
# We add a try-except block here to be robust, just in case.
try:
    import mind.governance.checks as checks_package
except ImportError as e:
    console.print(f"[bold red]CRITICAL FAILURE: Could not import the base checks package: {e}[/bold red]")
    sys.exit(1)


console.print(
    Panel(
        "[bold cyan]Auditor Discovery Diagnostic[/bold cyan]\n"
        "This script will attempt to import every check module individually.",
        border_style="cyan",
    )
)

all_ok = True
# Use pkgutil to find all modules in the checks package, just like the auditor does
for module_info in sorted(pkgutil.iter_modules(checks_package.__path__)):
    module_name = module_info.name
    full_module_path = f"mind.governance.checks.{module_name}"

    try:
        # Attempt to import the module
        importlib.import_module(full_module_path)
        console.print(f"[green]✅ PASS:[/green] Successfully imported [bold]{full_module_path}[/bold]")
    except ImportError as e:
        console.print(
            f"[bold red]❌ FAIL:[/bold red] Failed to import [bold]{full_module_path}[/bold]"
        )
        console.print(f"   [red]Error:[/red] {e}")
        console.print(
            "\n[bold yellow]This is the root cause of the problem.[/bold yellow]"
        )
        all_ok = False
        # Stop on the first failure to make the root cause obvious
        break
    except Exception as e:
        console.print(
            f"[bold red]❌ FAIL:[/bold red] An unexpected error occurred while importing [bold]{full_module_path}[/bold]"
        )
        console.print(f"   [red]Error:[/red] {type(e).__name__}: {e}")
        all_ok = False
        break

if all_ok:
    console.print(
        "\n[bold green]✅ All check modules were imported successfully.[/bold green]"
    )
    console.print(
        "This is highly unexpected. The issue might be in the auditor's class discovery logic itself."
    )