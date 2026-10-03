# src/cli/resources/docs/generate.py

"""
`core-admin docs generate` — regenerate the generated reference pages.

Renders both command trees with ``shared.cli.reference_markdown``:

- ``docs/reference/core-admin.md`` from the running ``core-admin`` tree;
- ``docs/reference/core.md`` from the installed core-cli package (the released
  ``core`` CLI, ADR-146), which must be importable — the page is never left
  silently stale because core-cli is missing.

and CORE's public API contract with ``api.openapi_document``:

- ``docs/reference/openapi.json`` (ADR-087 D9, amended 2026-10-03).

Dry-runs by default (reports which pages would change); ``--write`` writes
through FileHandler into CORE's own source checkout.
"""

from __future__ import annotations

import difflib

import typer
from rich.console import Console

from api.openapi_document import OPENAPI_DOCUMENT, render_openapi_document
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
    CORE_ADMIN_PAGE,
    CORE_CLI_PAGE,
    build_reference_pages,
)
from shared.cli.reference_markdown import load_core_cli_tree as _load_core_cli

from . import app


console = Console()

__all__ = [
    "CORE_ADMIN_PAGE",
    "CORE_CLI_PAGE",
    "OPENAPI_DOCUMENT",
    "generate_docs_command",
]


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
    summary="Regenerate the CLI reference pages and the OpenAPI contract.",
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
    """Regenerate the CLI reference pages and the OpenAPI contract.

    Writes docs/reference/core-admin.md (this CLI), docs/reference/core.md
    (the installed core-cli package) and docs/reference/openapi.json (CORE's
    public API contract). Runs from a CORE source checkout only, and needs
    core-cli installed (pip install core-cli).

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

    pages = build_reference_pages(ctx.find_root().command, core_cli)
    pages[OPENAPI_DOCUMENT] = render_openapi_document()

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
