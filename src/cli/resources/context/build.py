# src/body/cli/resources/context/build.py
"""
Context build command - Natural language context building.
UPDATED: Now correctly initializes CognitiveService for semantic search.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


def _format_context_for_display(packet: dict[str, Any]) -> str:
    """Format context packet for human readability."""
    lines = []
    header = packet.get("header", {})
    lines.append("=" * 80)
    lines.append("CONTEXT PACKAGE")
    lines.append("=" * 80)
    lines.append(f"Task: {header.get('task_id', 'unknown')}")
    lines.append(f"Goal: {packet.get('summary', 'No summary')}")
    lines.append(f"Items: {len(packet.get('context', []))}")
    lines.append(f"Mode: {header.get('mode', 'unknown')}")
    lines.append("")

    items = packet.get("context", [])
    if items:
        lines.append("## RELEVANT CODE")
        lines.append("")

        for idx, item in enumerate(items, 1):
            lines.append(f"### {idx}. {item.get('name', 'unknown')}")
            lines.append(f"Path: {item.get('path', 'unknown')}")
            lines.append(f"Type: {item.get('item_type', 'unknown')}")

            if item.get("content"):
                lines.append("```python")
                content = item["content"]
                lines.append(content)
                lines.append("```")
            else:
                lines.append("(No code content available)")
            lines.append("")

    stats = packet.get("provenance", {}).get("build_stats", {})
    if stats:
        lines.append("=" * 80)
        lines.append("STATS")
        lines.append(f"Build time: {stats.get('duration_ms', 0)}ms")
        lines.append(f"Total tokens: ~{stats.get('tokens_total', 0)}")

    return "\n".join(lines)


async def _build_async(
    query: str,
    output: str | None,
    max_tokens: int,
    max_items: int,
    no_cache: bool,
) -> None:
    """Async implementation of build command."""
    # 1. Setup Context
    core_context = create_core_context(service_registry)

    # 2. We must initialize the CognitiveService with a DB session to enable embeddings.
    async with service_registry.session() as session:
        cognitive = await service_registry.get_cognitive_service()
        await cognitive.initialize(session)

    console.print(f"[bold blue]🔍 Building context:[/bold blue] {query}")

    # 3. Build Context using the now-awake service
    context_service = core_context.context_service
    packet = await context_service.build_from_query(
        natural_query=query,
        max_tokens=max_tokens,
        max_items=max_items,
        use_cache=not no_cache,
    )

    # 4. Presentation
    formatted = _format_context_for_display(packet)

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
        console.print(f"[green]✅ Context written to {output}[/green]")
    else:
        console.print("")
        console.print(formatted)


# ID: e6f79e37-922c-454f-8caa-02357d28d300
async def build(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Natural language query"),
    output: str = typer.Option(None, "--output", "-o", help="Write to file"),
    max_tokens: int = typer.Option(30000, "--max-tokens", help="Token budget"),
    max_items: int = typer.Option(30, "--max-items", help="Max items"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache"),
) -> None:
    """Build context package from natural language query."""
    await _build_async(query, output, max_tokens, max_items, no_cache)
