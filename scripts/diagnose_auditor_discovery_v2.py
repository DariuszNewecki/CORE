# scripts/diagnose_auditor_discovery_v2.py
"""
A diagnostic script to test the importability and class discovery of all
constitutional checks to find the exact point of failure in the auditor's loop.
"""
import importlib
import inspect
import pkgutil
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

# Add the 'src' directory to the Python path to allow imports
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# We must import the base class to check against it
try:
    from mind.governance.checks.base_check import BaseCheck
    import mind.governance.checks as checks_package
except ImportError as e:
    console.print(f"[bold red]CRITICAL FAILURE: Could not import base components: {e}[/bold red]")
    sys.exit(1)

console.print(
    Panel(
        "[bold cyan]Auditor Discovery Diagnostic (v2: Class Inspection)[/bold cyan]\n"
        "This script will import each check and inspect its classes.",
        border_style="cyan",
    )
)

all_ok = True
# Use pkgutil to find all modules in the checks package
for module_info in sorted(pkgutil.iter_modules(checks_package.__path__)):
    module_name = module_info.name
    full_module_path = f"mind.governance.checks.{module_name}"

    try:
        # Step 1: Import the module
        module = importlib.import_module(full_module_path)
        console.print(f"[green]✅ PASS (Import):[/green] Successfully imported [bold]{full_module_path}[/bold]")

        # Step 2: Inspect the classes within the module
        console.print(f"   -> Inspecting classes in {module_name}...")
        found_check = False
        for member_name, member_class in inspect.getmembers(module, inspect.isclass):
            # --- START OF FIX ---
            # The variable name was corrected from 'member' to 'member_class'
            if member_class is not BaseCheck and issubclass(member_class, BaseCheck):
            # --- END OF FIX ---
                console.print(f"      [green]✓ Found Check:[/green] {member_name}")
                found_check = True
        
        if not found_check and not module_name.startswith('_'):
             console.print(f"      [yellow]ⓘ No check classes found in this module.[/yellow]")


    except Exception as e:
        console.print(
            f"[bold red]❌ FAIL (Inspection):[/bold red] An error occurred while inspecting [bold]{full_module_path}[/bold]"
        )
        console.print(f"   [red]Error:[/red] {type(e).__name__}: {e}")
        console.print(
            "\n[bold yellow]This is the root cause of the problem.[/bold yellow]"
        )
        all_ok = False
        # Stop on the first failure to make the root cause obvious
        break

if all_ok:
    console.print(
        "\n[bold green]✅ All check modules were imported and inspected successfully.[/bold green]"
    )
    console.print(
        "This is extremely unexpected. The issue is deeper than anticipated."
    )