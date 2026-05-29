# src/shared/cli/app_introspection.py

"""Pure introspection helpers for Typer applications.

Lives in shared/ so both the Body service that syncs commands to the DB
and the Mind engine that audits them consume the same walk. The walker
takes the Typer app as an argument — it does NOT import it — so this
module has no dependency on the CLI layer and triggers no CLI-side
module-load effects when imported.
"""

from __future__ import annotations

import inspect
from typing import Any

from shared.cli.command_meta import get_command_meta, infer_metadata_from_function
from shared.protocols.typer_protocols import TyperAppLike


# ID: 90345620-a400-47f6-a472-9c1b437301f0
def walk_typer_app(
    app: TyperAppLike,
    prefix: str = "",
    include_missing_handlers: bool = False,
) -> list[dict[str, Any]]:
    """Recursively enumerate every command in a Typer app.

    Returns one dict per command with the metadata fields needed by both
    DB sync and constitutional audit. The raw ``callback`` object is
    included so audit checks can interrogate it (e.g. detect coroutine
    functions for ``cli.async_execution``); DB-bound callers strip the
    callback before persisting.
    """
    commands: list[dict[str, Any]] = []

    for cmd_info in app.registered_commands:
        if not cmd_info.name:
            continue

        callback = cmd_info.callback
        full_name = f"{prefix}{cmd_info.name}"

        if not callback:
            if include_missing_handlers:
                commands.append(
                    {
                        "name": full_name,
                        "module": None,
                        "entrypoint": None,
                        "file_path": None,
                        "summary": None,
                        "category": prefix.replace(".", " ").strip() or "general",
                        "behavior": None,
                        "layer": None,
                        "aliases": [],
                        "dangerous": False,
                        "params_list": [],
                        "has_callback": False,
                        "has_explicit_meta": False,
                        "callback": None,
                    }
                )
            continue

        # Resolve file_path against the unwrapped callable so commands
        # wrapped by @core_command point at their own source file rather
        # than the decorator's. inspect.signature already follows
        # __wrapped__ by default; asyncio.iscoroutinefunction does not,
        # which is exactly what cli.async_execution needs to distinguish
        # a sync wrapper from a bare async callback — so the raw
        # ``callback`` is preserved in the returned dict.
        try:
            origin = inspect.unwrap(callback)
        except ValueError:
            origin = callback
        try:
            file_path: str | None = inspect.getfile(origin)
        except Exception:
            file_path = "unknown"

        sig = inspect.signature(callback)
        params_list = list(sig.parameters.keys())

        meta = get_command_meta(callback)

        if meta:
            source = meta
            summary = meta.summary
            category = meta.category
            has_explicit = True
        else:
            inferred = infer_metadata_from_function(
                func=callback, command_name=cmd_info.name, group_prefix=prefix
            )
            source = inferred
            summary = inferred.summary or (cmd_info.help or "").split("\n")[0]
            category = inferred.category
            has_explicit = False

        commands.append(
            {
                "name": source.canonical_name,
                "module": source.module or callback.__module__,
                "entrypoint": source.entrypoint or callback.__name__,
                "file_path": file_path,
                "summary": summary,
                "category": category or prefix.replace(".", " ").strip() or "general",
                "behavior": source.behavior.value,
                "layer": source.layer.value,
                "aliases": source.aliases or [],
                "dangerous": source.dangerous,
                "params_list": params_list,
                "has_callback": True,
                "has_explicit_meta": has_explicit,
                "callback": callback,
            }
        )

    for group_info in app.registered_groups:
        if group_info.name:
            new_prefix = f"{prefix}{group_info.name}."
            commands.extend(
                walk_typer_app(
                    group_info.typer_instance,
                    new_prefix,
                    include_missing_handlers=include_missing_handlers,
                )
            )

    return commands


__all__ = ["walk_typer_app"]
