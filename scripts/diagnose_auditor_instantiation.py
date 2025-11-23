# scripts/diagnose_auditor_instantiation.py
"""
A diagnostic script to test the full lifecycle of auditor checks:
1. Import the module.
2. Inspect the classes.
3. Instantiate each check class with a mock context.
This will reveal any hidden errors in the __init__ methods of the checks.
"""
import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

from rich.console import Console
from rich.panel import Panel

console = Console()

# Add the 'src' directory to the Python path
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
        "[bold cyan]Auditor Instantiation Diagnostic (v3)[/bold cyan]\n"
        "This script will import, inspect, and instantiate every check.",
        border_style="cyan",
    )
)

# Create a mock context that behaves like the real AuditorContext
mock_context = MagicMock()
mock_context.repo_path = project_root
mock_context.policies = {
    # Provide a minimal, valid policy structure to prevent errors
    "code_standards": {
        "naming_conventions": {},
        "dependency_injection": [] 
    }
}
mock_context.source_structure = {
    "entry_point_patterns": []
}
mock_context.symbols_list = []


all_ok = True
for module_info in sorted(pkgutil.iter_modules(checks_package.__path__)):
    module_name = module_info.name
    full_module_path = f"mind.governance.checks.{module_name}"

    try:
        # Step 1: Import the module
        module = importlib.import_module(full_module_path)
        console.print(f"[green]✅ PASS (Import):[/green] [bold]{full_module_path}[/bold]")

        # Step 2: Find and instantiate check classes
        for member_name, member_class in inspect.getmembers(module, inspect.isclass):
            if member_name != "BaseCheck" and issubclass(member_class, BaseCheck):
                console.print(f"   -> Found check class: [cyan]{member_name}[/cyan]")
                
                # Step 3: Attempt to instantiate the check
                try:
                    instance = member_class(mock_context)
                    console.print(f"      [green]✅ PASS (Instantiate):[/green] Successfully created an instance of {member_name}.")
                except Exception as e:
                    console.print(f"      [bold red]❌ FAIL (Instantiate):[/bold red] Failed to create an instance of [bold]{member_name}[/bold].")
                    console.print(f"         [red]Error:[/red] {type(e).__name__}: {e}")
                    console.print("\n[bold yellow]This is the root cause of the problem.[/bold yellow]")
                    all_ok = False
                    # Stop on the first failure
                    break
        if not all_ok:
            break

    except Exception as e:
        console.print(
            f"[bold red]❌ FAIL (Import/Inspect):[/bold red] An error occurred with [bold]{full_module_path}[/bold]"
        )
        console.print(f"   [red]Error:[/red] {type(e).__name__}: {e}")
        all_ok = False
        break

if all_ok:
    console.print(
        "\n[bold green]✅ All checks were imported and instantiated successfully.[/bold green]"
    )