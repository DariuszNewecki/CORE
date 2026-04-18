# src/cli/resources/context/build.py

"""
Context build command - Agent simulation mode.

Builds doctrine-aligned context packets and renders them for human / LAG use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from cli.utils import core_command
from shared.infrastructure.context.models import (
    ContextBuildRequest,
    PhaseType,
)
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)
console = Console()

TASK_TYPES = [
    "code_generation",
    "code_modification",
    "test_generation",
    "test.generate",
    "conversational",
]

_PHASE_BY_TASK: dict[str, PhaseType] = {
    "code_generation": "execution",
    "code_modification": "execution",
    "test_generation": "audit",
    "test.generate": "audit",
    "conversational": "runtime",
}


def _resolve_phase(task: str) -> PhaseType:
    return _PHASE_BY_TASK.get(task, "runtime")


def _format_item_source(item: dict[str, Any]) -> str:
    source = item.get("source", "unknown")
    score = item.get("score")
    score_str = f": {score:.2f}" if isinstance(score, int | float) else ""

    source_map = {
        "vector_search": f"🔍 vector search{score_str}",
        "database": "🗄️ database",
        "workspace": "✍️ workspace",
        "filesystem": "📄 filesystem",
        "unknown": "❓ unknown source",
    }
    return source_map.get(source, f"📎 {source}")


def _assemble_enriched_prompt(
    evidence: list[dict[str, Any]],
    file: str,
    symbol: str | None,
    task_type: str,
) -> str:
    deps: list[str] = []
    examples: list[str] = []
    existing_code = ""
    seen: set[str] = set()

    for item in evidence:
        name = item.get("name", "")
        path = item.get("path", "")
        content = item.get("content", "") or ""
        sig = item.get("signature", "") or ""

        if path == file and content:
            if symbol and name == symbol:
                existing_code = content
            elif not existing_code:
                existing_code = content

        if (
            name
            and name not in seen
            and item.get("item_type") in {"code", "symbol", "semantic_match"}
        ):
            seen.add(name)
            dep_line = f"- `{name}` from `{path}`"
            if sig:
                dep_line += f"\n  Signature: `{sig}`"
            deps.append(dep_line)

        if content and len(content) > 50 and item.get("item_type") == "code":
            block = [f"### {name}"]
            if item.get("summary"):
                block.append(str(item["summary"]))
            block.append("```python")
            block.append(content[:500])
            if len(content) > 500:
                block.append("# ... (truncated for display)")
            block.append("```")
            examples.append("\n".join(block))

    parts = [
        "# Code Task",
        "",
        (
            f"**Goal:** Implement or modify `{symbol}` in `{file}`"
            if symbol
            else f"**Goal:** Work in `{file}`"
        ),
        f"**Task type:** {task_type}",
        "",
    ]

    if deps:
        parts += ["## Available Dependencies", "\n".join(deps), ""]

    if examples:
        parts += ["## Relevant Code", "\n".join(examples), ""]

    if existing_code:
        parts += ["## Existing Code Context", "```python", existing_code, "```", ""]

    parts += [
        "## Requirements",
        "1. Return only valid Python code",
        "2. Include needed imports",
        "3. Include type hints and docstrings",
        "4. Respect CORE constitutional patterns",
        "",
        "## Target",
        f"Symbol: `{symbol}`" if symbol else "Symbol: `(file-level)`",
        f"Target file: `{file}`",
    ]
    return "\n".join(parts)


def _render_layer_constraints(section: Any) -> list[str]:
    if not isinstance(section, dict):
        return []

    layer = section.get("layer")
    rules = section.get("rules") or []
    if not layer or not rules:
        return []

    lines: list[str] = [
        f"## CONSTITUTIONAL CONSTRAINTS — {str(layer).upper()} layer",
        "",
        f"⛔ The following blocking rules apply to ALL files in the {layer} layer.",
        "These constraints are derived from file path alone and are authoritative",
        "regardless of role inference confidence.",
        "",
    ]

    for rule in rules:
        rid = rule.get("id") or "?"
        statement = rule.get("statement") or ""
        lines.append(f"{rid}: {statement}")

    warning = section.get("warning") or ""
    if warning:
        lines.append("")
        lines.append(f"⚠️  {warning}")

    lines.append("")
    return lines


def _format_packet_for_display(
    packet: dict[str, Any],
    file: str,
    symbol: str | None,
    task_type: str,
    show_prompt: bool,
) -> str:
    lines: list[str] = []

    header = packet.get("header", {})
    provenance = packet.get("provenance", {})
    stats = provenance.get("build_stats", {})
    evidence = packet.get("evidence", [])

    lines.append("=" * 80)
    lines.append("CORE CONTEXT PACKET  [Agent Simulation Mode]")
    lines.append("=" * 80)
    lines.append(f"Target file  : {file}")
    lines.append(f"Target symbol: {symbol or '(file-level)'}")
    lines.append(f"Task type    : {task_type}")
    lines.append(f"Phase        : {packet.get('phase', 'unknown')}")
    lines.append(f"Packet ID    : {header.get('packet_id', 'unknown')}")
    lines.append(f"Evidence     : {len(evidence)}")
    lines.append(f"Tokens (est) : ~{stats.get('tokens_total', 0)}")
    lines.append(f"Build time   : {stats.get('duration_ms', 0)}ms")
    lines.append("")

    for section_name in (
        "layer_constraints",
        "constitution",
        "policy",
        "constraints",
        "runtime",
    ):
        section = packet.get(section_name)
        if section_name == "layer_constraints":
            rendered = _render_layer_constraints(section)
            if rendered:
                lines.extend(rendered)
            continue
        if section:
            lines.append(f"## {section_name.upper()}")
            lines.append("```json")
            lines.append(json.dumps(section, indent=2, sort_keys=True, default=str))
            lines.append("```")
            lines.append("")

    if not evidence:
        lines.append("[!] No evidence collected.")
        lines.append("")
    else:
        lines.append("## EVIDENCE")
        lines.append("")
        for idx, item in enumerate(evidence, 1):
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
                lines.append(f"Summary: {str(summary)[:160]}")
            lines.append("")
            if content:
                lines.append("```python")
                lines.append(content)
                lines.append("```")
            else:
                lines.append("(No code content available)")
            lines.append("")

    if show_prompt:
        lines.append("=" * 80)
        lines.append("ASSEMBLED PROMPT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(_assemble_enriched_prompt(evidence, file, symbol, task_type))
        lines.append("")

    lines.append("=" * 80)
    lines.append("STATS")
    source_counts: dict[str, int] = {}
    for item in evidence:
        src = item.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in sorted(source_counts.items()):
        lines.append(f"  {src}: {count}")

    return "\n".join(lines)


@app.command("build")
@command_meta(
    canonical_name="context.build",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Simulate exact context CoderAgent sees.",
)
@core_command(dangerous=False, requires_context=False)
# ID: 945e6c12-26e2-423d-ad3e-0cb10faaccb1
async def build_cmd(
    ctx: typer.Context,
    file: str = typer.Option(..., "--file", "-f", help="Target file path"),
    symbol: str | None = typer.Option(
        None, "--symbol", "-s", help="Target symbol name"
    ),
    task: str = typer.Option(
        "code_modification", "--task", "-t", help=f"Task type: {', '.join(TASK_TYPES)}"
    ),
    goal: str = typer.Option("", "--goal", "-g", help="Optional goal override"),
    show_prompt: bool = typer.Option(
        False, "--show-prompt", help="Also show assembled LLM prompt"
    ),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Write output to file instead of stdout"
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass context cache"),
    max_tokens: int = typer.Option(
        30000, "--max-tokens", help="Token budget (display only)"
    ),
    max_items: int = typer.Option(20, "--max-items", help="Max evidence items hint"),
) -> None:
    if task not in TASK_TYPES:
        logger.info("Unknown task type: %s", task)
        raise typer.Exit(code=1)

    from shared.infrastructure.database.session_manager import get_session

    service_registry.prime(get_session)
    core_context = create_core_context(service_registry)

    async with service_registry.session() as session:
        cognitive = await service_registry.get_cognitive_service()
        await cognitive.initialize(session)

    console.print(
        Panel(
            f"[bold]File:[/bold]   {file}\n[bold]Symbol:[/bold] {symbol or '(file-level)'}\n[bold]Task:[/bold]   {task}",
            title="[bold blue]🔬 Building Agent Context[/bold blue]",
            expand=False,
        )
    )

    request = ContextBuildRequest(
        goal=goal
        or (f"{task} for {symbol} in {file}" if symbol else f"{task} for {file}"),
        trigger="cli",
        phase=_resolve_phase(task),
        target_files=[file],
        target_symbols=[symbol] if symbol else [],
        include_constitution=True,
        include_policy=True,
        include_symbols=True,
        include_vectors=True,
        include_runtime=True,
    )

    packet_obj = await core_context.context_service.build(
        request,
        use_cache=not no_cache,
    )

    packet = {
        "header": packet_obj.header,
        "phase": packet_obj.request.phase,
        "layer_constraints": packet_obj.layer_constraints,
        "constitution": packet_obj.constitution,
        "policy": packet_obj.policy,
        "constraints": packet_obj.constraints,
        "evidence": packet_obj.evidence[:max_items],
        "runtime": packet_obj.runtime,
        "provenance": packet_obj.provenance,
    }

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
            rel_output,
            formatted,
        )
        logger.info("✅ Context written to %s", output)
    else:
        logger.info("")
        logger.info(formatted)
