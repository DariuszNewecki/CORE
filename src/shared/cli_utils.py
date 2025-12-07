# src/shared/cli_utils.py
"""
Constitutional CLI Framework - The Single Source of Truth for Commands.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import typer
from rich.console import Console
from rich.prompt import Confirm

from shared.action_types import ActionResult
from shared.context import CoreContext
from shared.logger import getLogger


# CLI Utilities are allowed to use Console for interaction
console = Console(log_time=False, log_path=False)
logger = getLogger(__name__)

# Type hint for the decorated function
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
# ID: dca404bc-b4dd-4241-8f98-aa2f220f4430
class CommandMetadata:
    """Metadata stored for each CLI command."""

    dangerous: bool
    confirmation: bool
    requires_context: bool


# Global registry for command discovery and governance
COMMAND_REGISTRY: dict[str, CommandMetadata] = {}


# ID: 995ae6d4-7f07-4656-8e31-ecdc30578e6c
def core_command(
    *,
    dangerous: bool = False,
    confirmation: bool = False,
    requires_context: bool = True,
):
    """
    The ONE decorator to rule them all.
    """

    # ID: f365748d-cc91-4aaa-b9a5-c80afe0368ea
    def decorator(func: F) -> F:
        # Register for governance visibility
        COMMAND_REGISTRY[func.__name__] = CommandMetadata(
            dangerous=dangerous,
            confirmation=confirmation,
            requires_context=requires_context,
        )

        @functools.wraps(func)
        # ID: 04b00743-f330-474c-b56f-52c7d5617baf
        def wrapper(*args, **kwargs) -> Any:
            # Extract Typer Context from args or kwargs
            ctx: typer.Context | None = next(
                (arg for arg in args if isinstance(arg, typer.Context)),
                kwargs.get("ctx"),
            )

            # If not found in args, check if we can inject it (Typer usually passes it if requested)
            if not ctx:
                # In some Typer setups, ctx might not be passed if not asked for.
                # We warn but try to proceed (graceful degradation for simple commands)
                # But for core commands requiring context, we must fail.
                if requires_context:
                    console.print(
                        "[bold red]System Error: CLI command must accept 'ctx: typer.Context'[/bold red]"
                    )
                    raise typer.Exit(1)

            core_context: CoreContext | None = (
                ctx.obj if ctx and requires_context else None
            )

            # Constitutional safety check for dangerous operations
            write = kwargs.get("write", False)
            if dangerous and not write:
                console.print(
                    "[bold yellow]⚠️  DRY RUN MODE[/bold yellow]\n"
                    "   No changes will be made. Use [cyan]--write[/cyan] to apply.\n"
                )

            # Interactive confirmation for dangerous operations
            if dangerous and confirmation and write:
                if not confirm_action(
                    "[bold red]🚨 CONFIRM DANGEROUS OPERATION[/bold red]\n"
                    "   This will modify your codebase. Continue?",
                    abort_message="Operation cancelled by user.",
                ):
                    raise typer.Exit(0)

            # --- REFACTORED EXECUTION LOGIC ---

            async def _run_in_unified_loop():
                """Runs injection and execution in the SAME loop."""

                # 1. JIT Injection
                if core_context and core_context.registry:
                    try:
                        # 1. Qdrant
                        if core_context.qdrant_service is None:
                            qdrant = await core_context.registry.get_qdrant_service()
                            core_context.qdrant_service = qdrant

                        # 2. Cognitive Service (depends on Qdrant)
                        if core_context.cognitive_service is None:
                            cognitive = (
                                await core_context.registry.get_cognitive_service()
                            )
                            core_context.cognitive_service = cognitive

                        # 3. Auditor Context (The Mind)
                        if core_context.auditor_context is None:
                            if hasattr(core_context.registry, "get_auditor_context"):
                                auditor = (
                                    await core_context.registry.get_auditor_context()
                                )
                                core_context.auditor_context = auditor
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: JIT Service Injection failed: {e}[/yellow]"
                        )

                # 2. Execute Command
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            # Determine execution strategy
            try:
                # Check if we are ALREADY in a loop (e.g. FastAPI)
                try:
                    loop = asyncio.get_running_loop()
                    # We are in a loop -> Schedule the task
                    # Note: returning a Task/Coroutine to Typer might not work as expected
                    # unless Typer is in async mode. For standard CLI usage, we usually
                    # aren't in a loop yet.
                    if asyncio.iscoroutinefunction(func):
                        return loop.create_task(_run_in_unified_loop())
                    else:
                        # Sync function in async loop? Just run it.
                        # But we can't await the injection...
                        # This edge case is rare in CLI.
                        raise RuntimeError(
                            "Cannot run synchronous CLI command inside an existing async loop with async injection."
                        )
                except RuntimeError:
                    # No loop running -> Use asyncio.run() for the WHOLE block
                    result = asyncio.run(_run_in_unified_loop())

                # Handle ActionResult constitutional formatting
                if isinstance(result, ActionResult):
                    _display_action_result(result)
                    if not result.ok:
                        raise typer.Exit(1)
                elif result is not None:
                    # Non-ActionResult return - just print it
                    console.print(result)

                return result

            except typer.Exit:
                raise
            except Exception as e:
                console.print("\n[bold red]❌ Command failed unexpectedly:[/bold red]")
                console.print(f"   {type(e).__name__}: {e}")
                # Show traceback if debug
                import traceback

                console.print(traceback.format_exc())
                raise typer.Exit(1)

        return wrapper

    return decorator


# ID: 66ad8653-546c-4605-a52b-1d3a896af0a3
def confirm_action(message: str, *, abort_message: str = "Aborted.") -> bool:
    """Unified confirmation prompt for dangerous operations."""
    console.print()  # Valid spacing
    confirmed = Confirm.ask(message)
    if not confirmed:
        console.print(f"[yellow]{abort_message}[/yellow]")
    console.print()  # Valid spacing
    return confirmed


def _display_action_result(result: ActionResult) -> None:
    """Constitutional formatting for ActionResult objects."""
    name = result.action_id or "Command"

    # Handle dry-run vs write modes
    dry_run = (
        result.data.get("dry_run", False) if isinstance(result.data, dict) else False
    )

    if result.ok:
        if "error" in result.data:
            console.print(
                f"[bold yellow]⚠️  {name} completed with warnings[/bold yellow]"
            )
        elif "violations_found" in result.data:
            violations = result.data["violations_found"]
            if violations == 0:
                console.print(f"[bold green]✅ {name}[/bold green]: All checks passed")
            elif dry_run:
                console.print(
                    f"[yellow]📋 {name}[/yellow]: {violations} violations found (dry-run)"
                )
            else:
                fixed = result.data.get("fixed_count", 0)
                console.print(
                    f"[bold green]✅ {name}[/bold green]: Fixed {fixed}/{violations} violations"
                )
        elif "ids_assigned" in result.data:
            count = result.data["ids_assigned"]
            console.print(f"[bold green]✅ {name}[/bold green]: {count} IDs assigned")
        elif "files_modified" in result.data:
            files = result.data["files_modified"]
            console.print(f"[bold green]✅ {name}[/bold green]: Modified {files} files")
        else:
            console.print(f"[bold green]✅ {name}[/bold green]: Completed successfully")
    else:
        error = (
            result.data.get("error", "Unknown error")
            if isinstance(result.data, dict)
            else str(result.data)
        )
        console.print(f"\n[bold red]❌ {name} FAILED[/bold red]")
        console.print(f"   Error: {error}")
        if hasattr(result, "suggestions") and result.suggestions:
            console.print("\n[dim]Suggestions:[/dim]")
            for suggestion in result.suggestions:
                console.print(f"   • {suggestion}")


# --- Helper Functions ---


# ID: 9457b9d1-bbe4-454e-8c91-2477b65ef20a
def display_error(msg: str):
    console.print(f"[bold red]{msg}[/bold red]")


# ID: 412cae3d-95aa-4116-87df-254804b73f99
def display_success(msg: str):
    console.print(f"[bold green]{msg}[/bold green]")


# ID: 5d180779-7b25-4dac-91e4-856badd7146e
def display_info(msg: str):
    console.print(f"[cyan]{msg}[/cyan]")


# ID: fe5c00ee-6880-4262-af7e-393287a75ea7
def display_warning(msg: str):
    console.print(f"[yellow]{msg}[/yellow]")


# FIX: Restore async_command functionality for legacy commands!
# ID: 0cf5ce27-6a19-4bf0-9e6f-7f69100d8b11
def async_command(func: Callable) -> Callable:
    """
    Decorator for legacy async commands.
    Wraps async functions in asyncio.run() so Typer can execute them.
    """

    @functools.wraps(func)
    # ID: e0bd5031-93aa-4f3a-b682-795052e53c6e
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper
