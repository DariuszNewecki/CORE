# src/shared/cli_utils/decorators.py
"""
Constitutional CLI Decorators.

Provides the @core_command and @async_command wrappers which manage
the asyncio lifecycle, JIT service injection, and database teardown.
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

from .display import _display_action_result
from .prompts import confirm_action


logger = getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")


@dataclass
# ID: 858a8748-1c63-461d-9101-dd6e742d6315
class CommandMetadata:
    dangerous: bool
    confirmation: bool
    requires_context: bool


COMMAND_REGISTRY: dict[str, CommandMetadata] = {}


# ID: fb0ffe71-cd19-4f82-b36e-11bb9b424821
def core_command(
    *,
    dangerous: bool = False,
    confirmation: bool = False,
    requires_context: bool = True,
):
    """
    Primary constitutional wrapper for CORE CLI commands.
    """

    # ID: e5c51712-e73d-44d2-97a9-82b48817646d
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        COMMAND_REGISTRY[func.__name__] = CommandMetadata(
            dangerous, confirmation, requires_context
        )

        @functools.wraps(func)
        # ID: 77ebffad-b3e8-4cc7-8835-f49770a2a653
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            ctx = next(
                (a for a in args if isinstance(a, typer.Context)), kwargs.get("ctx")
            )
            if ctx is None:
                try:
                    ctx = typer.get_current_context()
                except Exception:
                    ctx = None
            if requires_context and (not ctx):
                logger.info(
                    "[bold red]System Error: CLI command must accept 'ctx: typer.Context'[/bold red]"
                )
                raise typer.Exit(1)
            write = bool(cast(dict[str, Any], kwargs).get("write", False))
            if dangerous and (not write):
                logger.info(
                    "[bold yellow]⚠️  DRY RUN MODE[/bold yellow]\n   No changes will be made. Use [cyan]--write[/cyan] to apply.\n"
                )
            if dangerous and confirmation and write:
                yes = bool(cast(dict[str, Any], kwargs).get("yes", False))
                if not yes:
                    if not confirm_action(
                        "[bold red]🚨 CONFIRM DANGEROUS OPERATION[/bold red]\n   Continue?",
                        abort_message="Cancelled.",
                    ):
                        raise typer.Exit(0)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                if asyncio.iscoroutinefunction(func):
                    return cast(Any, func)(*args, **kwargs)
                return cast(Any, func)(*args, **kwargs)

            async def _run_with_teardown():
                try:
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
                    res = (
                        await cast(Any, func)(*args, **kwargs)
                        if asyncio.iscoroutinefunction(func)
                        else cast(Any, func)(*args, **kwargs)
                    )
                    if isinstance(res, ActionResult):
                        _display_action_result(res)
                        if not res.ok:
                            raise typer.Exit(1)
                    elif res is not None:
                        logger.info(res)
                    return res
                finally:
                    if ctx and ctx.obj:
                        for attr in [
                            "qdrant_service",
                            "cognitive_service",
                            "auditor_context",
                        ]:
                            if hasattr(ctx.obj, attr):
                                setattr(ctx.obj, attr, None)
                        if hasattr(ctx.obj, "registry"):
                            registry = ctx.obj.registry
                            if hasattr(registry, "_instances"):
                                registry._instances.clear()
                    await asyncio.sleep(0)
                    await dispose_engine()

            try:
                return cast(R, asyncio.run(_run_with_teardown()))
            except typer.Exit:
                raise
            except Exception as e:
                logger.info(
                    "\n[bold red]❌ Command failed:[/bold red]\n   %s: %s",
                    type(e).__name__,
                    e,
                )
                logger.error(traceback.format_exc())
                raise typer.Exit(1)

        return wrapper

    return decorator


# ID: 530827c4-1788-449c-aaca-4e44d0e6fd5d
def async_command(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Simpler async wrapper for non-core commands that still need loop management.
    """

    @functools.wraps(func)
    # ID: fad2065e-ee80-4b3f-8e82-75f3e2ffa768
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return func(*args, **kwargs)
        return asyncio.run(func(*args, **kwargs))

    return wrapper
