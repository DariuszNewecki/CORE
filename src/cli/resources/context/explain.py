# src/cli/resources/context/explain.py
"""
Context explain command - Natural language exploration.

Answers "what code relates to this concept?" via semantic search.
Uses build_from_query() — vector search over the knowledge graph.

This is an EXPLORATION tool, not an agent simulation.
For agent simulation (what CoderAgent sees), use: core-admin context build

USAGE:
    core-admin context explain "how does policy enforcement work"
    core-admin context explain "constitutional violation detection" --max-items 10
    core-admin context explain "how are assumptions extracted" --output var/exploration.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from shared.cli_utils import core_command
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)
console = Console()


def _format_exploration_for_display(packet: dict[str, Any]) -> str:
    """Format exploration packet for human readability."""
    lines: list[str] = []
    header = packet.get("header", {})
    stats = packet.get("provenance", {}).get("build_stats", {})
    items = packet.get("context", [])
    lines.append("=" * 80)
    lines.append("CONTEXT EXPLORATION")
    lines.append("=" * 80)
    lines.append(f"Query  : {packet.get('problem', {}).get('summary', 'No summary')}")
    lines.append(f"Items  : {len(items)}")
    lines.append(f"Tokens : ~{stats.get('tokens_total', 0)}")
    lines.append(f"Mode   : {header.get('mode', 'HISTORICAL')}")
    lines.append("")
    if not items:
        lines.append("[!] No results found. Try different search terms.")
        lines.append(
            "    Ensure vectors are up to date: core-admin vectors vectorize --write"
        )
        return "\n".join(lines)
    lines.append("## RELEVANT CODE")
    lines.append("")
    for idx, item in enumerate(items, 1):
        name = item.get("name", "unknown")
        path = item.get("path", "unknown")
        item_type = item.get("item_type", "unknown")
        content = item.get("content", "")
        summary = item.get("summary", "")
        lines.append(f"### {idx}. {path}::{name}")
        lines.append(f"Type: {item_type}")
        if summary:
            lines.append(f"Summary: {summary[:120]}")
        lines.append("")
        if content:
            lines.append("```python")
            lines.append(content)
            lines.append("```")
        else:
            lines.append("(No code content available)")
        lines.append("")
    lines.append("=" * 80)
    lines.append(f"Build time: {stats.get('duration_ms', 0)}ms")
    return "\n".join(lines)


@app.command("explain")
@command_meta(
    canonical_name="context.explain",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Explore codebase by concept using semantic search.",
)
@core_command(dangerous=False, requires_context=False)
# ID: f36a0b23-f6e7-4813-a75c-4482f78b41f4
async def explain_cmd(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Natural language query"),
    output: str = typer.Option(None, "--output", "-o", help="Write to file"),
    max_tokens: int = typer.Option(30000, "--max-tokens", help="Token budget"),
    max_items: int = typer.Option(30, "--max-items", help="Max items"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache"),
) -> None:
    """
    Explore codebase by concept using semantic search.

    Answers "what code relates to this concept?" — useful for understanding
    unfamiliar parts of the codebase before making changes.

    For simulating what the agent sees during code generation,
    use: core-admin context build --file ... --symbol ...
    """
    from shared.infrastructure.database.session_manager import get_session

    service_registry.prime(get_session)
    core_context = create_core_context(service_registry)
    async with service_registry.session() as session:
        cognitive = await service_registry.get_cognitive_service()
        await cognitive.initialize(session)
    logger.info("[bold blue]🔍 Exploring:[/bold blue] %s", query)
    packet = await core_context.context_service.build_from_query(
        natural_query=query,
        max_tokens=max_tokens,
        max_items=max_items,
        use_cache=not no_cache,
    )
    formatted = _format_exploration_for_display(packet)
    if output:
        output_path = Path(output)
        repo_root = Path(core_context.git_service.repo_path).resolve()
        resolved = (
            (repo_root / output_path).resolve()
            if not output_path.is_absolute()
            else output_path.resolve()
        )
        if not resolved.is_relative_to(repo_root):
            raise ValueError(f"Output path is outside repository boundary: {output}")
        rel_output = resolved.relative_to(repo_root).as_posix()
        FileHandler(str(core_context.git_service.repo_path)).write_runtime_text(
            rel_output, formatted
        )
        logger.info("[green]✅ Exploration written to %s[/green]", output)
    else:
        logger.info("")
        logger.info(formatted)
