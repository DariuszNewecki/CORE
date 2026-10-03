# src/cli/resources/docs/generate.py

"""
`core-admin docs generate` — regenerate the CLI reference pages.

Renders both command trees with ``shared.cli.reference_markdown``:

- ``docs/reference/core-admin.md`` from the running ``core-admin`` tree;
- ``docs/reference/core.md`` from the installed core-cli package (the released
  ``core`` CLI, ADR-146), which must be importable — the page is never left
  silently stale because core-cli is missing.

Dry-runs by default (reports which pages would change); ``--write`` writes
through FileHandler into CORE's own source checkout.
"""

from __future__ import annotations

import difflib
import importlib
import importlib.metadata
import importlib.util

import typer
from rich.console import Console

from body.infrastructure.storage.file_handler import FileHandler
from cli.logic.byor import core_source_root
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.cli.reference_markdown import (
    Command,
    click_command_for,
    render_cli_reference,
)

from . import app


console = Console()

CORE_ADMIN_PAGE = "docs/reference/core-admin.md"
CORE_CLI_PAGE = "docs/reference/core.md"

_CORE_ADMIN_INTRO = (
    "The operator CLI, shipped in `core-runtime`. Generated from the command tree "
    "in this repository; see the [CLI overview](../cli-reference.md) for which "
    "binary does what."
)


def _core_cli_intro(version: str) -> str:
    return (
        f"The consumer CLI, shipped in `core-cli` (this page: version {version}, the "
        "released package). Most commands talk to a running CORE API. See the "
        "[CLI overview](../cli-reference.md) for which binary does what."
    )


def _load_core_cli() -> tuple[Command, str] | None:
    """The installed core-cli command tree and its version, or None if absent."""
    if importlib.util.find_spec("core_cli") is None:
        return None
    core_cli_main = importlib.import_module("core_cli.main")
    return click_command_for(core_cli_main.app), importlib.metadata.version("core-cli")


def _change_summary(old: str | None, new: str) -> str:
    if old is None:
        return "new"
    if old == new:
        return "unchanged"
    added = removed = 0
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm=""):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return f"changed (+{added} / -{removed} lines)"


@app.command("generate")
@command_meta(
    canonical_name="docs.generate",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    # Writes into CORE's own source checkout — an operator surface.
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Regenerate the CLI reference pages from the live command trees.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=False)
# ID: 0cd24900-c622-40cd-8fde-6653c6c1e52a
async def generate_docs_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Write the pages. Without --write, reports which pages would change.",
    ),
) -> None:
    """Regenerate the CLI reference pages from the live command trees.

    Writes docs/reference/core-admin.md (this CLI) and docs/reference/core.md
    (the installed core-cli package). Runs from a CORE source checkout only,
    and needs core-cli installed (pip install core-cli).

    Example: core-admin docs generate --write
    """
    core_root = core_source_root()
    if core_root is None:
        console.print(
            "[bold red]docs generate runs from a CORE source checkout;[/bold red] "
            "this install has no repository to write docs into."
        )
        raise typer.Exit(1)
    core_cli = _load_core_cli()
    if core_cli is None:
        console.print(
            "[bold red]core-cli is not installed[/bold red] — the `core` reference is "
            "generated from the released package. Install it with "
            "[cyan]pip install core-cli[/cyan] and rerun."
        )
        raise typer.Exit(1)

    core_cli_root, core_cli_version = core_cli
    pages = {
        CORE_ADMIN_PAGE: render_cli_reference(
            ctx.find_root().command, "core-admin", _CORE_ADMIN_INTRO
        ),
        CORE_CLI_PAGE: render_cli_reference(
            core_cli_root,
            "core",
            _core_cli_intro(core_cli_version),
        ),
    }

    handler = FileHandler(str(core_root))
    for rel_path, content in pages.items():
        target = core_root / rel_path
        old = target.read_text(encoding="utf-8") if target.exists() else None
        summary = _change_summary(old, content)
        if write and old != content:
            handler.write_runtime_text(rel_path, content)
            console.print(f"[green]wrote[/green] {rel_path} — {summary}")
        else:
            console.print(f"{rel_path} — {summary}")
    if not write:
        console.print("Pass [cyan]--write[/cyan] to write the pages.")
