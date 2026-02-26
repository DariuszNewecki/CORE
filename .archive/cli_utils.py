# src/shared/cli_utils.py
"""
Constitutional CLI Framework - The Single Source of Truth for Commands.

Runtime invariants (robustness):
- CLI commands run deterministically under a single owned event loop (asyncio.run()).
- Sync Typer entrypoints MUST NOT return asyncio Tasks.
- Loop-bound resources (e.g., DB pool) must be disposed before the loop closes.
"""

from __future__ import annotations

import asyncio
import functools
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar, cast

import typer
from rich.console import Console
from rich.prompt import Confirm

from shared.action_types import ActionResult
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import dispose_engine
from shared.logger import getLogger


console = Console(log_time=False, log_path=False)
logger = getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
# ID: dca404bc-b4dd-4241-8f98-aa2f220f4430
class CommandMetadata:
    """Metadata stored for each CLI command."""

    dangerous: bool
    confirmation: bool
    requires_context: bool


# Global registry for command discovery and governance
COMMAND_REGISTRY: dict[str, CommandMetadata] = {}


def _get_typer_ctx(
    args: tuple[Any, ...], kwargs: dict[str, Any]
) -> typer.Context | None:
    return next((a for a in args if isinstance(a, typer.Context)), kwargs.get("ctx"))


def _display_action_result(result: ActionResult) -> None:
    """Constitutional formatting for ActionResult objects."""
    name = result.action_id or "Command"

    dry_run = (
        result.data.get("dry_run", False) if isinstance(result.data, dict) else False
    )

    if result.ok:
        if isinstance(result.data, dict) and "error" in result.data:
            console.print(
                f"[bold yellow]⚠️  {name} completed with warnings[/bold yellow]"
            )
        elif isinstance(result.data, dict) and "violations_found" in result.data:
            violations = int(result.data["violations_found"])
            if violations == 0:
                console.print(f"[bold green]✅ {name}[/bold green]: All checks passed")
            elif dry_run:
                console.print(
                    f"[yellow]📋 {name}[/yellow]: {violations} violations found (dry-run)"
                )
            else:
                fixed = int(result.data.get("fixed_count", 0))
                console.print(
                    f"[bold green]✅ {name}[/bold green]: Fixed {fixed}/{violations} violations"
                )
        elif isinstance(result.data, dict) and "ids_assigned" in result.data:
            console.print(
                f"[bold green]✅ {name}[/bold green]: {int(result.data['ids_assigned'])} IDs assigned"
            )
        elif isinstance(result.data, dict) and "files_modified" in result.data:
            console.print(
                f"[bold green]✅ {name}[/bold green]: Modified {int(result.data['files_modified'])} files"
            )
        else:
            console.print(f"[bold green]✅ {name}[/bold green]: Completed successfully")
    else:
        if isinstance(result.data, dict):
            error = str(result.data.get("error", "Unknown error"))
        else:
            error = str(result.data)

        console.print(f"\n[bold red]❌ {name} FAILED[/bold red]")
        console.print(f"   Error: {error}")

        suggestions = getattr(result, "suggestions", None)
        if suggestions:
            console.print("\n[dim]Suggestions:[/dim]")
            for suggestion in suggestions:
                console.print(f"   • {suggestion}")


# ID: 66ad8653-546c-4605-a52b-1d3a896af0a3
def confirm_action(message: str, *, abort_message: str = "Aborted.") -> bool:
    """Unified confirmation prompt for dangerous operations."""
    console.print()
    confirmed = Confirm.ask(message)
    if not confirmed:
        console.print(f"[yellow]{abort_message}[/yellow]")
    console.print()
    return confirmed


# ID: 995ae6d4-7f07-4656-8e31-ecdc30578e6c
def core_command(
    *,
    dangerous: bool = False,
    confirmation: bool = False,
    requires_context: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    The ONE decorator to rule them all.

    Guarantees:
    - Owns the event loop via asyncio.run().
    - Never nests inside an existing running loop.
    - Always disposes loop-bound DB engine before loop close.
    - Supports sync and async command implementations.
    """

    # ID: 200ae65e-0258-4f33-a743-a0148d02e46e
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        COMMAND_REGISTRY[func.__name__] = CommandMetadata(
            dangerous=dangerous,
            confirmation=confirmation,
            requires_context=requires_context,
        )

        @functools.wraps(func)
        # ID: 04b00743-f330-474c-b56f-52c7d5617baf
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            ctx = _get_typer_ctx(args, cast(dict[str, Any], kwargs))
            if requires_context and not ctx:
                console.print(
                    "[bold red]System Error: CLI command must accept 'ctx: typer.Context'[/bold red]"
                )
                raise typer.Exit(1)

            core_context: CoreContext | None = (
                ctx.obj if (ctx and requires_context) else None
            )

            write = bool(cast(dict[str, Any], kwargs).get("write", False))

            if dangerous and not write:
                console.print(
                    "[bold yellow]⚠️  DRY RUN MODE[/bold yellow]\n"
                    "   No changes will be made. Use [cyan]--write[/cyan] to apply.\n"
                )

            if dangerous and confirmation and write:
                if not confirm_action(
                    "[bold red]🚨 CONFIRM DANGEROUS OPERATION[/bold red]\n"
                    "   This will modify your codebase. Continue?",
                    abort_message="Operation cancelled by user.",
                ):
                    raise typer.Exit(0)

            # Enforce "single loop owner" invariant: CLI never runs inside a running loop.
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                raise RuntimeError(
                    "CORE CLI commands cannot run inside an already-running event loop. "
                    "From async contexts, call the underlying async function directly (do not invoke Typer)."
                )

            async def _run_in_unified_loop() -> Any:
                """
                Runs optional DI injection and execution in the SAME owned loop.
                """
                if core_context and getattr(core_context, "registry", None):
                    try:
                        if getattr(core_context, "qdrant_service", None) is None:
                            core_context.qdrant_service = (
                                await core_context.registry.get_qdrant_service()
                            )

                        if getattr(core_context, "cognitive_service", None) is None:
                            core_context.cognitive_service = (
                                await core_context.registry.get_cognitive_service()
                            )

                        if getattr(
                            core_context, "auditor_context", None
                        ) is None and hasattr(
                            core_context.registry, "get_auditor_context"
                        ):
                            core_context.auditor_context = (
                                await core_context.registry.get_auditor_context()
                            )
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: JIT Service Injection failed: {e}[/yellow]"
                        )

                if asyncio.iscoroutinefunction(func):
                    return await cast(Any, func)(*args, **kwargs)

                # Sync function: run it directly inside the owned loop (no tasks returned).
                return cast(Any, func)(*args, **kwargs)

            async def _run_with_teardown() -> Any:
                try:
                    result = await _run_in_unified_loop()

                    if isinstance(result, ActionResult):
                        _display_action_result(result)
                        if not result.ok:
                            raise typer.Exit(1)
                    elif result is not None:
                        console.print(result)

                    return result
                finally:
                    # Deterministic teardown for loop-bound resources
                    try:
                        await dispose_engine()
                    except Exception as e:
                        logger.debug("DB engine dispose failed (non-fatal): %s", e)

            try:
                return cast(R, asyncio.run(_run_with_teardown()))
            except typer.Exit:
                raise
            except Exception as e:
                console.print("\n[bold red]❌ Command failed unexpectedly:[/bold red]")
                console.print(f"   {type(e).__name__}: {e}")
                console.print(traceback.format_exc())
                raise typer.Exit(1)

        return wrapper

    return decorator


# --- Helper Functions ---


# ID: 9457b9d1-bbe4-454e-8c91-2477b65ef20a
def display_error(msg: str) -> None:
    console.print(f"[bold red]{msg}[/bold red]")


# ID: 412cae3d-95aa-4116-87df-254804b73f99
def display_success(msg: str) -> None:
    console.print(f"[bold green]{msg}[/bold green]")


# ID: 5d180779-7b25-4dac-91e4-856badd7146e
def display_info(msg: str) -> None:
    console.print(f"[cyan]{msg}[/cyan]")


# ID: fe5c00ee-6880-4262-af7e-393287a75ea7
def display_warning(msg: str) -> None:
    console.print(f"[yellow]{msg}[/yellow]")


# FIX: Restore async_command functionality for legacy commands!
# NOTE: Prefer @core_command for full runtime guarantees.
# ID: 0cf5ce27-6a19-4bf0-9e6f-7f69100d8b11
def async_command(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator for legacy async commands.

    Safety:
    - Refuses to nest inside an already running loop (same invariant as core_command).
    """

    @functools.wraps(func)
    # ID: e0bd5031-93aa-4f3a-b682-795052e53c6e
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            raise RuntimeError(
                "async_command cannot run inside an already-running event loop. "
                "Call the coroutine directly from async contexts."
            )
        return asyncio.run(func(*args, **kwargs))

    return wrapper
