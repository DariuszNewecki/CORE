# src/shared/cli_utils/decorators.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890

"""
Constitutional CLI Decorators.

Provides the @core_command and @async_command wrappers which manage
the asyncio lifecycle, JIT service injection, and database teardown.

HEALED (V2.6.2):
- Hardened teardown to prevent SAWarning during garbage collection.
- Explicitly nullifies Context references to drop DB session pointers.
- Disposes the engine loop-locally and yields to the loop for cleanup.
"""

from __future__ import annotations

import asyncio
import functools
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar, cast

import typer

from shared.action_types import ActionResult
from shared.infrastructure.database.session_manager import dispose_engine
from shared.logger import getLogger

from .display import _display_action_result, console
from .prompts import confirm_action


logger = getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")


@dataclass
# ID: 9c16bece-1e37-46c0-83d9-2de435d2d7e3
class CommandMetadata:
    dangerous: bool
    confirmation: bool
    requires_context: bool


COMMAND_REGISTRY: dict[str, CommandMetadata] = {}


# ID: c675b73e-1b6d-41c9-b15c-a326e9c75b5a
def core_command(
    *,
    dangerous: bool = False,
    confirmation: bool = False,
    requires_context: bool = True,
):
    """
    Primary constitutional wrapper for CORE CLI commands.
    """

    # ID: 41b496b7-333a-453e-8bd2-149c4ce382e2
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        COMMAND_REGISTRY[func.__name__] = CommandMetadata(
            dangerous, confirmation, requires_context
        )

        @functools.wraps(func)
        # ID: 52793c73-6d19-4c28-96cd-e8af74666c9f
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # 1. Context & Security Logic
            ctx = next(
                (a for a in args if isinstance(a, typer.Context)), kwargs.get("ctx")
            )
            if requires_context and not ctx:
                console.print(
                    "[bold red]System Error: CLI command must accept 'ctx: typer.Context'[/bold red]"
                )
                raise typer.Exit(1)

            write = bool(cast(dict[str, Any], kwargs).get("write", False))
            if dangerous and not write:
                console.print(
                    "[bold yellow]⚠️  DRY RUN MODE[/bold yellow]\n   No changes will be made. Use [cyan]--write[/cyan] to apply.\n"
                )
            if dangerous and confirmation and write:
                if not confirm_action(
                    "[bold red]🚨 CONFIRM DANGEROUS OPERATION[/bold red]\n   Continue?",
                    abort_message="Cancelled.",
                ):
                    raise typer.Exit(0)

            # 2. Loop Management
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                raise RuntimeError(
                    "CORE CLI commands cannot run inside an already-running event loop."
                )

            async def _run_with_teardown():
                try:
                    # JIT Service Injection
                    if ctx and ctx.obj and hasattr(ctx.obj, "registry"):
                        core_context = ctx.obj
                        if getattr(core_context, "qdrant_service", None) is None:
                            core_context.qdrant_service = (
                                await core_context.registry.get_qdrant_service()
                            )
                        if getattr(core_context, "cognitive_service", None) is None:
                            core_context.cognitive_service = (
                                await core_context.registry.get_cognitive_service()
                            )
                        if getattr(core_context, "auditor_context", None) is None:
                            core_context.auditor_context = (
                                await core_context.registry.get_auditor_context()
                            )

                    # Execution
                    res = (
                        await cast(Any, func)(*args, **kwargs)
                        if asyncio.iscoroutinefunction(func)
                        else cast(Any, func)(*args, **kwargs)
                    )

                    # Results
                    if isinstance(res, ActionResult):
                        _display_action_result(res)
                        if not res.ok:
                            raise typer.Exit(1)
                    elif res is not None:
                        console.print(res)
                    return res
                finally:
                    # HEALED V2.6.2: Aggressive cleanup
                    if ctx and ctx.obj:
                        # 1. Clear service references from the Context object
                        for attr in [
                            "qdrant_service",
                            "cognitive_service",
                            "auditor_context",
                        ]:
                            if hasattr(ctx.obj, attr):
                                setattr(ctx.obj, attr, None)

                        # 2. Clear the global Service Registry
                        if hasattr(ctx.obj, "registry"):
                            registry = ctx.obj.registry
                            if hasattr(registry, "_instances"):
                                registry._instances.clear()

                    # 3. Final disposal
                    await dispose_engine()
                    await asyncio.sleep(0)  # Yield to loop for final GC

            try:
                return cast(R, asyncio.run(_run_with_teardown()))
            except typer.Exit:
                raise
            except Exception as e:
                console.print(
                    f"\n[bold red]❌ Command failed:[/bold red]\n   {type(e).__name__}: {e}"
                )
                logger.error(traceback.format_exc())
                raise typer.Exit(1)

        return wrapper

    return decorator


# ID: 34db7c54-cd1f-42af-9690-05d8c97c4ea4
def async_command(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    # ID: ea2838f1-6fc0-410e-8119-edcc198a3097
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            raise RuntimeError(
                "async_command cannot run inside an already-running event loop."
            )
        return asyncio.run(func(*args, **kwargs))

    return wrapper
