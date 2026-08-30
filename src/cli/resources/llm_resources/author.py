# src/cli/resources/llm_resources/author.py
"""
core-admin llm-resources validate / author — #821 Unit 3.

Reads an llm_resources definition from a JSON file and validates it
against the capability taxonomy and the table's own CHECK-constraint
rules (mirrored client-side by validate_llm_resource_definition), then
optionally persists it with --apply. core.llm_resources is DB-authoritative
(ADR-052 §1) -- there is no YAML source to diff against, unlike
cognitive-roles; this is a clean authoring surface, not a projection.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from .hub import app


console = Console()


# ID: 8e2b6d0a-4c9e-4b3f-a5d9-3c7e1f5b9d3a
def _load_definition(definition_file: Path) -> dict:
    try:
        return json.loads(definition_file.read_text(encoding="utf-8"))
    except OSError as exc:
        console.print(f"[bold red]Cannot read {definition_file}:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except json.JSONDecodeError as exc:
        console.print(
            f"[bold red]Malformed JSON in {definition_file}:[/bold red] {exc}"
        )
        raise typer.Exit(1) from exc


# ID: 9f3c7e1f-5b0a-4c6d-b8e0-4d8f2b6c0e4a
def _render_result(data: dict) -> None:
    if data.get("valid"):
        console.print(f"[bold green]Valid:[/bold green] {data.get('name', '')}")
    else:
        console.print(f"[bold red]Invalid:[/bold red] {data.get('name', '')}")
        for violation in data.get("violations", []):
            console.print(f"  - {violation}")
    resource = data.get("resource")
    if resource:
        console.print(resource)


@app.command(
    "validate", help="Validate an llm_resources definition without persisting it."
)
@core_command(dangerous=False, requires_context=False)
# ID: 0a4d8f2b-6c1e-4d9f-c0f2-5b9d3f7c1e6a
async def llm_resources_validate(
    ctx: typer.Context,
    definition_file: Path = typer.Argument(
        ..., help="Path to a JSON file describing the llm_resources row."
    ),
) -> None:
    """Validate a definition file; exits 1 if invalid."""
    definition = _load_definition(definition_file)
    client = CoreApiClient()
    response = await client.llm_resources.author(definition=definition, write=False)
    data = response.get("data", {})
    _render_result(data)
    if not data.get("valid", False):
        raise typer.Exit(1)


@app.command(
    "author", help="Validate and, with --apply, persist an llm_resources definition."
)
@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: 1b5e9d3f-7c2a-4e0d-d1a3-6c0e4a8d2f7b
async def llm_resources_author(
    ctx: typer.Context,
    definition_file: Path = typer.Argument(
        ..., help="Path to a JSON file describing the llm_resources row."
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Persist the definition to core.llm_resources (otherwise behaves like validate).",
    ),
) -> None:
    """Without --apply: same as `validate`. With --apply: creates or updates the row."""
    definition = _load_definition(definition_file)
    client = CoreApiClient()
    response = await client.llm_resources.author(definition=definition, write=apply)
    data = response.get("data", {})
    _render_result(data)

    if not apply:
        console.print(
            "[yellow]Dry-run: pass --apply to persist this definition.[/yellow]"
        )
        return

    if not data.get("valid", False):
        raise typer.Exit(1)
