# src/body/cli/commands/fix/handler_discovery.py
"""
Action handler discovery and registration commands for the 'fix' CLI group.

Provides:
- core-admin fix discover-handlers
- core-admin fix register-handlers (Iteration 2 - not yet implemented)
- core-admin fix validate-handlers (Iteration 3 - not yet implemented)

Part of Solution 2: Automatic Capability Assignment for Action Handlers
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from . import console, fix_app, handle_command_errors

# Re-export for use in this module
__all__ = [
    "discover_handlers_command",
    "register_handlers_command",
    "validate_handlers_command",
]


# ============================================================================
# Discovery Logic (Embedded to avoid import issues)
# ============================================================================


# ID: 1f572417-a0f0-4859-80cd-9109c3d85beb
class HandlerInfo:
    """Container for handler metadata"""

    def __init__(
        self,
        class_name: str,
        module_path: str,
        file_path: Path,
        handler_name: str | None = None,
        docstring: str | None = None,
        has_execute: bool = False,
    ):
        self.class_name = class_name
        self.module_path = module_path
        self.file_path = file_path
        self.handler_name = handler_name
        self.docstring = docstring
        self.has_execute = has_execute
        self.is_registered = False
        self.domain = self._extract_domain()

    def _extract_domain(self) -> str:
        """Extract domain from module path"""
        # src/body/actions/healing_actions.py -> body.actions.healing
        parts = self.module_path.replace("src/", "").replace(".py", "").split("/")
        if len(parts) >= 3:
            return f"{parts[0]}.{parts[1]}.{parts[2].replace('_actions', '')}"
        return "body.actions.unknown"


# ID: 090701bf-702c-4012-89ed-639448642a13
class ActionHandlerDiscovery:
    """Discovers all ActionHandler implementations in the codebase"""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.actions_dir = repo_root / "src" / "body" / "actions"
        self.handlers: list[HandlerInfo] = []
        self.registered_handlers: set[str] = set()

    # ID: 10d4af53-3dc9-41ce-ad85-a358d1537dba
    def discover_all(self) -> list[HandlerInfo]:
        """Main discovery workflow"""
        self._load_registered_handlers()
        self._scan_handler_files()
        self._mark_registration_status()
        return self.handlers

    def _load_registered_handlers(self):
        """Extract handler class names from ActionRegistry._register_handlers()"""
        registry_file = self.actions_dir / "registry.py"

        if not registry_file.exists():
            console.print("[red]❌ ActionRegistry not found![/red]")
            return

        try:
            tree = ast.parse(registry_file.read_text())

            # Find the _register_handlers method in the ActionRegistry class
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.FunctionDef)
                    and node.name == "_register_handlers"
                ):
                    # Look through the function body for assignments
                    for stmt in node.body:
                        if isinstance(stmt, ast.AnnAssign):
                            # Handle annotated assignment: handlers_to_register: list[type[ActionHandler]] = [...]
                            if (
                                isinstance(stmt.target, ast.Name)
                                and stmt.target.id == "handlers_to_register"
                            ):
                                if isinstance(stmt.value, ast.List):
                                    for elt in stmt.value.elts:
                                        if isinstance(elt, ast.Name):
                                            self.registered_handlers.add(elt.id)
                        elif isinstance(stmt, ast.Assign):
                            # Handle regular assignment: handlers_to_register = [...]
                            for target in stmt.targets:
                                if (
                                    isinstance(target, ast.Name)
                                    and target.id == "handlers_to_register"
                                ):
                                    if isinstance(stmt.value, ast.List):
                                        for elt in stmt.value.elts:
                                            if isinstance(elt, ast.Name):
                                                self.registered_handlers.add(elt.id)

            if self.registered_handlers:
                console.print(
                    f"[green]✅ Found {len(self.registered_handlers)} registered handlers[/green]"
                )
            else:
                console.print(
                    "[yellow]⚠️  No registered handlers found - check registry.py syntax[/yellow]"
                )

        except Exception as e:
            console.print(f"[red]❌ Failed to parse registry: {e}[/red]")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    def _scan_handler_files(self):
        """Scan all Python files in actions directory"""
        python_files = [
            f
            for f in self.actions_dir.glob("*.py")
            if f.name not in ("base.py", "context.py", "registry.py", "__init__.py")
        ]

        for file_path in python_files:
            self._parse_handler_file(file_path)

    def _parse_handler_file(self, file_path: Path):
        """Parse a single Python file for ActionHandler classes"""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
            module_path = str(file_path.relative_to(self.repo_root))

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    base_names = [self._get_name(base) for base in node.bases]

                    if "ActionHandler" in base_names:
                        handler_info = self._extract_handler_info(
                            node, module_path, file_path, content
                        )
                        if handler_info:
                            self.handlers.append(handler_info)
        except Exception:
            pass  # Silent fail for unparseable files

    def _get_name(self, node: ast.expr) -> str:
        """Extract name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _extract_handler_info(
        self,
        class_node: ast.ClassDef,
        module_path: str,
        file_path: Path,
        source_code: str,
    ) -> HandlerInfo | None:
        """Extract metadata from a handler class"""
        docstring = ast.get_docstring(class_node)
        handler_name = None
        has_execute = False

        for node in class_node.body:
            if isinstance(node, ast.FunctionDef) and node.name == "name":
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Return) and stmt.value:
                        if isinstance(stmt.value, ast.Constant):
                            handler_name = stmt.value.value

            if isinstance(node, ast.FunctionDef) and node.name == "execute":
                has_execute = True

        return HandlerInfo(
            class_name=class_node.name,
            module_path=module_path,
            file_path=file_path,
            handler_name=handler_name,
            docstring=docstring,
            has_execute=has_execute,
        )

    def _mark_registration_status(self):
        """Mark which handlers are registered"""
        for handler in self.handlers:
            handler.is_registered = handler.class_name in self.registered_handlers


# ============================================================================
# CLI Commands
# ============================================================================


@fix_app.command(
    "discover-handlers",
    help="Discover all ActionHandler implementations and report registration status.",
)
@handle_command_errors
# ID: c8ac3fe0-bd53-4455-8a16-db4955db8d7c
def discover_handlers_command(
    save_json: bool = typer.Option(
        True,
        "--save-json/--no-save-json",
        help="Save JSON report to reports/ directory",
    ),
):
    """
    Scan src/body/actions/ for ActionHandler classes and compare with ActionRegistry.

    This is a **read-only diagnostic tool** that makes no changes to code or database.

    Identifies:
    - Active handlers (registered in ActionRegistry)
    - Orphaned handlers (exist in code but not registered)

    Output:
    - Console table showing all handlers
    - JSON report (if --save-json)

    Examples:
        poetry run core-admin fix discover-handlers
        poetry run core-admin fix discover-handlers --no-save-json
    """
    console.print("[bold cyan]🔍 Discovering Action Handlers...[/bold cyan]\n")

    try:
        from shared.config import settings

        repo_root = settings.REPO_PATH

        # Run discovery
        discovery = ActionHandlerDiscovery(repo_root)
        handlers = discovery.discover_all()

        # Separate active and orphaned
        active = [h for h in handlers if h.is_registered]
        orphaned = [h for h in handlers if not h.is_registered]

        # Summary Panel
        summary = f"""
[bold]Total Handlers Found:[/bold] {len(handlers)}
[bold green]Active (Registered):[/bold green] {len(active)}
[bold yellow]Orphaned (Unregistered):[/bold yellow] {len(orphaned)}
        """
        console.print(Panel(summary, title="📊 Discovery Summary", border_style="cyan"))

        # Active Handlers Table
        if active:
            console.print("\n[bold green]✅ ACTIVE HANDLERS (Registered)[/bold green]")
            table = Table(show_header=True, header_style="bold green")
            table.add_column("Class Name", style="cyan")
            table.add_column("Handler Name", style="green")
            table.add_column("Domain", style="blue")
            table.add_column("File", style="white")

            for h in sorted(active, key=lambda x: x.domain):
                table.add_row(
                    h.class_name,
                    h.handler_name or "[dim]Not found[/dim]",
                    h.domain,
                    h.file_path.name,
                )
            console.print(table)

        # Orphaned Handlers Table
        if orphaned:
            console.print(
                "\n[bold yellow]⚠️  ORPHANED HANDLERS (Not Registered)[/bold yellow]"
            )
            table = Table(show_header=True, header_style="bold yellow")
            table.add_column("Class Name", style="cyan")
            table.add_column("Handler Name", style="yellow")
            table.add_column("Domain", style="blue")
            table.add_column("File", style="white")

            for h in sorted(orphaned, key=lambda x: x.domain):
                table.add_row(
                    h.class_name,
                    h.handler_name or "[dim]Not found[/dim]",
                    h.domain,
                    h.file_path.name,
                )
            console.print(table)

        # Save JSON report
        if save_json:
            report_file = repo_root / "reports" / "handler_discovery.json"
            report_file.parent.mkdir(exist_ok=True)

            report_data = {
                "summary": {
                    "total": len(handlers),
                    "active": len(active),
                    "orphaned": len(orphaned),
                },
                "handlers": [
                    {
                        "class_name": h.class_name,
                        "handler_name": h.handler_name,
                        "domain": h.domain,
                        "module_path": h.module_path,
                        "is_registered": h.is_registered,
                        "has_execute": h.has_execute,
                    }
                    for h in handlers
                ],
            }

            report_file.write_text(json.dumps(report_data, indent=2))
            console.print(f"\n[green]📄 Report saved: {report_file}[/green]")

        # Next steps guidance
        console.print("\n[bold cyan]📋 NEXT STEPS:[/bold cyan]")
        console.print(
            "1. Review orphaned handlers - are they dead code or missing from registry?"
        )
        console.print(
            "2. Run: [bold]poetry run core-admin fix register-handlers --dry-run[/bold]"
        )
        console.print("3. This will show what capability definitions would be created")

        console.print("\n[bold green]✅ Discovery complete![/bold green]")

    except Exception as e:
        console.print(f"\n[bold red]❌ Discovery failed: {e}[/bold red]")
        raise typer.Exit(code=1)


@fix_app.command(
    "register-handlers",
    help="Register action handlers as capabilities in the Mind (NOT YET IMPLEMENTED).",
)
@handle_command_errors
# ID: 7a5b983f-dae3-4194-9397-9577674a5441
def register_handlers_command(
    status: str = typer.Option(
        "active",
        "--status",
        help="Which handlers to register: 'active', 'all', or 'orphaned'",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="Preview changes without committing to database",
    ),
):
    """
    Create capability definitions for discovered action handlers.

    **STATUS: Iteration 2 - Not Yet Implemented**

    This command will:
    - Create capability entries in the database
    - Link handler execute() methods to capabilities via symbol_capability_links
    - Ensure Mind-Body synchronization

    Examples:
        poetry run core-admin fix register-handlers --status active --dry-run
        poetry run core-admin fix register-handlers --status all --execute
    """
    console.print("[bold yellow]⚠️  ITERATION 2: Not yet implemented[/bold yellow]\n")
    console.print("This command will create capability definitions for handlers.")
    console.print("\nPlease run discovery first:")
    console.print("  [bold]poetry run core-admin fix discover-handlers[/bold]")


@fix_app.command(
    "validate-handlers",
    help="Validate Mind-Body alignment for action handlers (NOT YET IMPLEMENTED).",
)
@handle_command_errors
# ID: 70925922-5d2f-4498-9930-9b0705096708
def validate_handlers_command():
    """
    Verify that all registered handlers have corresponding capability definitions.

    **STATUS: Iteration 3 - Not Yet Implemented**

    This command will:
    - Check registry vs database alignment
    - Flag missing capability definitions
    - Detect orphaned capabilities

    Part of ongoing maintenance workflow in `make dev-sync`.

    Examples:
        poetry run core-admin fix validate-handlers
    """
    console.print("[bold yellow]⚠️  ITERATION 3: Not yet implemented[/bold yellow]\n")
    console.print("This command will verify Mind-Body handler alignment.")
    console.print("\nPlease run discovery first:")
    console.print("  [bold]poetry run core-admin fix discover-handlers[/bold]")
