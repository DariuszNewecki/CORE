# src/cli/resources/context/build.py
"""
Context build command - Agent simulation mode.

Simulates EXACTLY what CoderAgent sees before code generation.
Uses build_for_task() — the same code path as the autonomous agent —
NOT build_from_query() which is a weaker exploration path.

PURPOSE:
    You are working with AI assistants (Claude, DeepSeek) on a 100k+ LOC codebase.
    Before asking an AI to work on a specific symbol or file, run this command
    to get the exact context slice the agent would receive. Paste that output
    to the AI. It now has surgical precision instead of guessing.

USAGE:
    # Simulate what CoderAgent sees for a specific symbol
    core-admin context build \\
        --file src/mind/governance/authority_package_builder.py \\
        --symbol AuthorityPackageBuilder \\
        --task code_modification

    # Also show the assembled LLM prompt
    core-admin context build \\
        --file src/will/cli_logic/reviewer.py \\
        --symbol constitutional_review \\
        --task code_generation \\
        --show-prompt

    # Write output to file for sharing with Claude/DeepSeek
    core-admin context build \\
        --file src/shared/infrastructure/context/service.py \\
        --symbol ContextService \\
        --task code_modification \\
        --output var/context_for_claude.md
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from shared.cli_utils import core_command
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)
console = Console()

# Valid task types — mirrors CoderAgent task_type_map
TASK_TYPES = [
    "code_generation",
    "code_modification",
    "test_generation",
    "test.generate",
    "conversational",
]


# ID: context-build-format-source
def _format_item_source(item: dict[str, Any]) -> str:
    """Human-readable explanation of WHY this item was included."""
    source = item.get("source", "unknown")
    score = item.get("score")
    score_str = f": {score:.2f}" if score else ""
    source_map = {
        # Actual names emitted by ContextBuilder
        "qdrant": f"🔍 vector search / Qdrant (semantic{score_str})",
        "db_query": "🗄️  DB lookup (direct / graph)",
        # Legacy / alternative names
        "builtin_ast": "📄 force-added (target file AST)",
        "db_direct": "🗄️  DB lookup (direct match)",
        "db_graph": "🕸️  DB graph traversal (dependency)",
        "vector_search": f"🔍 vector search (semantic{score_str})",
        "ast_scope": "🔬 AST scope analysis",
        "unknown": "❓ unknown source",
    }
    return source_map.get(source, f"📎 {source}")


# ID: context-build-format-packet
def _format_packet_for_display(
    packet: dict[str, Any],
    file: str,
    symbol: str | None,
    task_type: str,
    show_prompt: bool,
) -> str:
    """
    Format the context packet as a developer telescope output.

    Shows:
    - What was assembled and why (source attribution per item)
    - The actual prompt that would be sent to the LLM (if --show-prompt)
    - Build stats
    """
    lines: list[str] = []
    header = packet.get("header", {})
    provenance = packet.get("provenance", {})
    stats = provenance.get("build_stats", {})
    items = packet.get("context", [])

    lines.append("=" * 80)
    lines.append("CORE CONTEXT PACKAGE  [Agent Simulation Mode]")
    lines.append("=" * 80)
    lines.append(f"Target file  : {file}")
    lines.append(f"Target symbol: {symbol or '(file-level)'}")
    lines.append(f"Task type    : {task_type}")
    lines.append(f"Packet ID    : {header.get('task_id', 'unknown')}")
    lines.append(f"Items        : {len(items)}")
    lines.append(f"Tokens (est) : ~{stats.get('tokens_total', 0)}")
    lines.append(f"Build time   : {stats.get('duration_ms', 0)}ms")
    lines.append("")

    if not items:
        lines.append("[!] No context items collected.")
        lines.append("    Check that the file path is correct and the DB is synced.")
        lines.append("    Run: make dev-sync")
    else:
        lines.append("## CONTEXT ITEMS")
        lines.append("")

        for idx, item in enumerate(items, 1):
            name = item.get("name", "unknown")
            path = item.get("path", "unknown")
            item_type = item.get("item_type", "unknown")
            summary = item.get("summary", "")
            content = item.get("content", "")
            source_label = _format_item_source(item)

            lines.append(f"### {idx}. {path}::{name}")
            lines.append(f"Type   : {item_type}")
            lines.append(f"Source : {source_label}")
            if summary:
                lines.append(f"Summary: {summary[:120]}")
            lines.append("")

            if content:
                lines.append("```python")
                lines.append(content)
                lines.append("```")
            else:
                lines.append("(No code content available — symbol may need re-sync)")
            lines.append("")

    if show_prompt:
        lines.append("=" * 80)
        lines.append("ASSEMBLED PROMPT  [What the LLM receives]")
        lines.append("=" * 80)
        lines.append("")
        prompt = _assemble_enriched_prompt(items, file, symbol, task_type)
        lines.append(prompt)
        lines.append("")

    lines.append("=" * 80)
    lines.append("STATS")
    source_counts: dict[str, int] = {}
    for item in items:
        src = item.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in sorted(source_counts.items()):
        lines.append(f"  {src}: {count}")

    return "\n".join(lines)


# ID: context-build-assemble-prompt
def _assemble_enriched_prompt(
    items: list[dict[str, Any]],
    file: str,
    symbol: str | None,
    task_type: str,
) -> str:
    """
    Assemble the enriched prompt exactly as build_enriched_prompt() would.
    This is what DeepSeek/Claude Coder actually receives.
    """
    deps: list[str] = []
    similar: list[str] = []
    existing_code: str = ""
    seen: set[str] = set()

    for item in items:
        name = item.get("name", "")
        path = item.get("path", "")
        content = item.get("content", "")
        sig = item.get("signature", "")

        # Existing code: prefer exact symbol name match, fall back to first item in target file
        if path == file and content:
            if symbol and name == symbol:
                existing_code = content  # exact match — always wins
            elif not existing_code:
                existing_code = content  # fallback — first item in target file

        # Dependencies
        if name and name not in seen and item.get("item_type") in ("code", "symbol"):
            seen.add(name)
            dep_line = f"- `{name}` from `{path}`"
            if sig:
                dep_line += f"\n  Signature: `{sig}`"
            deps.append(dep_line)

        # Similar symbols (items with actual code content)
        if content and len(content) > 50 and item.get("item_type") == "code":
            summary = item.get("summary", "")
            block = [f"### {name}"]
            if summary:
                block.append(summary)
            block.append("```python")
            block.append(content[:500])
            if len(content) > 500:
                block.append("# ... (truncated for display)")
            block.append("```")
            similar.append("\n".join(block))

    parts = [
        "# Code Generation Task",
        "",
        (
            f"**Goal:** Implement `{symbol}` in `{file}`"
            if symbol
            else f"**Goal:** Work in `{file}`"
        ),
        f"**Task type:** {task_type}",
        "",
    ]

    if deps:
        parts += ["## Available Dependencies", "\n".join(deps), ""]

    if similar:
        parts += ["## Similar Implementations (for reference)", "\n".join(similar), ""]

    if existing_code:
        parts += [
            "## Existing Code Context",
            "```python",
            existing_code,
            "```",
            "",
        ]

    parts += [
        "## Implementation Requirements",
        "1. Return ONLY valid Python code",
        "2. Include all necessary imports",
        "3. Include docstrings and type hints",
        "4. Follow constitutional patterns",
        "5. Use similar implementations as reference (not verbatim)",
        "",
        "## Code to Generate",
        f"Symbol: `{symbol}`" if symbol else "Symbol: `(file-level)`",
        f"Target file: `{file}`",
    ]

    return "\n".join(parts)


# ID: context-build-command
@app.command("build")
@command_meta(
    canonical_name="context.build",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Simulate exact context CoderAgent sees — use before asking AI to work on a symbol.",
)
@core_command(dangerous=False, requires_context=False)
# ID: ee369b65-c289-46d2-bf9a-d82a66552654
async def build_cmd(
    ctx: typer.Context,
    file: str = typer.Option(
        ...,
        "--file",
        "-f",
        help="Target file path (e.g. src/mind/governance/authority_package_builder.py)",
    ),
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        "-s",
        help="Target symbol name (e.g. AuthorityPackageBuilder)",
    ),
    task: str = typer.Option(
        "code_modification",
        "--task",
        "-t",
        help=f"Task type: {', '.join(TASK_TYPES)}",
    ),
    goal: str = typer.Option(
        "",
        "--goal",
        "-g",
        help="Optional: describe what you want to do (improves vector search relevance)",
    ),
    show_prompt: bool = typer.Option(
        False,
        "--show-prompt",
        help="Also show the assembled LLM prompt (what DeepSeek/Coder receives)",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to file instead of stdout",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass context cache"),
    max_tokens: int = typer.Option(30000, "--max-tokens", help="Token budget"),
    max_items: int = typer.Option(20, "--max-items", help="Max context items"),
) -> None:
    """
    Build agent context — simulate exactly what CoderAgent sees.

    Uses build_for_task() (same path as autonomous agent), NOT semantic search.
    Outputs the context packet with source attribution per item,
    and optionally the assembled LLM prompt.

    Use this before asking Claude/DeepSeek to work on a specific symbol.
    """
    if task not in TASK_TYPES:
        console.print(
            f"[red]Unknown task type: {task}[/red]\n"
            f"Valid types: {', '.join(TASK_TYPES)}"
        )
        raise typer.Exit(code=1)

    from shared.infrastructure.database.session_manager import get_session

    service_registry.prime(get_session)
    core_context = create_core_context(service_registry)

    async with service_registry.session() as session:
        cognitive = await service_registry.get_cognitive_service()
        await cognitive.initialize(session)

    console.print(
        Panel(
            f"[bold]File:[/bold]   {file}\n"
            f"[bold]Symbol:[/bold] {symbol or '(file-level)'}\n"
            f"[bold]Task:[/bold]   {task}",
            title="[bold blue]🔬 Building Agent Context[/bold blue]",
            expand=False,
        )
    )

    # task_spec mirrors CoderAgent._build_context_package() exactly
    task_spec: dict[str, Any] = {
        "task_id": f"inspect_{uuid.uuid4().hex[:8]}",
        "task_type": task,
        "target_file": file,
        "target_symbol": symbol,
        "summary": goal
        or (
            f"Inspect context for {symbol} in {file}"
            if symbol
            else f"Inspect file-level context for {file}"
        ),
        "scope": {
            "traversal_depth": 2,
            "include": [file],
        },
        "constraints": {
            "max_tokens": max_tokens,
            "max_items": max_items,
        },
    }

    packet = await core_context.context_service.build_for_task(
        task_spec, use_cache=not no_cache
    )

    formatted = _format_packet_for_display(packet, file, symbol, task, show_prompt)

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
