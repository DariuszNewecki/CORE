#!/usr/bin/env python3
"""
eval_context_build.py - Evaluation harness for 'core-admin context build'.

PURPOSE:
    Runs context build against two known CORE symbols and saves the full output
    to var/eval_context_build.md so Claude can evaluate correctness.

USAGE:
    poetry run python eval_context_build.py

WHAT IS EVALUATED:
    For each test case, we check:
    1. TARGET FOUND    - The target symbol itself appears in items (force-add via AST)
    2. HAS DEPS        - At least one dependency found (graph traversal working)
    3. HAS VECTORS     - At least one vector/semantic hit (Qdrant working)
    4. PROMPT COHERENT - The assembled prompt contains required sections
    5. NO EMPTY ITEMS  - No items with missing content

    These signals tell us whether DB sync, graph traversal, and vector search
    are all functioning correctly in the context pipeline.
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from pathlib import Path
from typing import Any


# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


# ---------------------------------------------------------------------------
# Test Cases — pick symbols that are well-known and well-synced in CORE
# ---------------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "ContextService (infrastructure core)",
        "file": "src/shared/infrastructure/context/service.py",
        "symbol": "ContextService",
        "task": "code_modification",
        "goal": "Understand how ContextService builds packets",
    },
    {
        "name": "AuthorityPackageBuilder (governance core)",
        "file": "src/mind/governance/authority_package_builder.py",
        "symbol": "AuthorityPackageBuilder",
        "task": "code_modification",
        "goal": "Add a new validation gate to the authority builder",
    },
]


# ---------------------------------------------------------------------------
# Evaluation Criteria
# ---------------------------------------------------------------------------
def evaluate_packet(
    packet: dict[str, Any],
    file: str,
    symbol: str,
    task_type: str,
) -> dict[str, Any]:
    """Run evaluation checks on a built packet. Returns pass/fail per criterion."""
    items = packet.get("context", [])
    stats = packet.get("provenance", {}).get("build_stats", {})

    results: dict[str, Any] = {
        "item_count": len(items),
        "tokens_est": stats.get("tokens_total", 0),
        "duration_ms": stats.get("duration_ms", 0),
        "checks": {},
    }

    # CHECK 1: Target symbol found (AST force-add)
    target_found = any(
        item.get("name") == symbol or item.get("path") == file for item in items
    )
    results["checks"]["target_found"] = {
        "pass": target_found,
        "detail": f"Symbol '{symbol}' or file '{file}' present in items",
    }

    # CHECK 2: Has dependency items (graph traversal or DB lookup)
    # ContextBuilder emits "db_query" for DB hits, "db_graph"/"db_direct" are legacy names
    dep_items = [
        i
        for i in items
        if i.get("source") in ("db_query", "db_graph", "db_direct")
        and i.get("name") != symbol
    ]
    results["checks"]["has_dependencies"] = {
        "pass": len(dep_items) > 0,
        "detail": f"{len(dep_items)} dependency items found (db_query / db_graph / db_direct)",
    }

    # CHECK 3: Has vector hits (Qdrant working)
    # ContextBuilder emits "qdrant" — "vector_search" is legacy name
    vector_items = [i for i in items if i.get("source") in ("qdrant", "vector_search")]
    results["checks"]["has_vector_hits"] = {
        "pass": len(vector_items) > 0,
        "detail": f"{len(vector_items)} vector search hits found (qdrant / vector_search)",
    }

    # CHECK 4: No items with empty content
    empty_items = [
        i for i in items if not i.get("content") and i.get("item_type") == "code"
    ]
    results["checks"]["no_empty_content"] = {
        "pass": len(empty_items) == 0,
        "detail": f"{len(empty_items)} code items with empty content",
    }

    # CHECK 5: Packet has valid header
    header = packet.get("header", {})
    has_header = bool(header.get("task_id") and header.get("task_type"))
    results["checks"]["valid_header"] = {
        "pass": has_header,
        "detail": f"task_id={header.get('task_id')}, task_type={header.get('task_type')}",
    }

    # Summary
    passed = sum(1 for c in results["checks"].values() if c["pass"])
    total = len(results["checks"])
    results["score"] = f"{passed}/{total}"
    results["overall"] = (
        "PASS" if passed == total else "PARTIAL" if passed > 0 else "FAIL"
    )

    return results


# ---------------------------------------------------------------------------
# Prompt Assembly (mirrors build.py logic)
# ---------------------------------------------------------------------------
def assemble_prompt(items: list[dict], file: str, symbol: str, task: str) -> str:
    deps, similar, existing_code = [], [], ""
    seen: set[str] = set()

    for item in items:
        name = item.get("name", "")
        path = item.get("path", "")
        content = item.get("content", "")
        sig = item.get("signature", "")

        if path == file and content:
            if name == symbol:
                existing_code = content  # exact match — always wins
            elif not existing_code:
                existing_code = content  # fallback

        if name and name not in seen and item.get("item_type") in ("code", "symbol"):
            seen.add(name)
            dep = f"- `{name}` from `{path}`"
            if sig:
                dep += f"\n  Signature: `{sig}`"
            deps.append(dep)

        if content and len(content) > 50 and item.get("item_type") == "code":
            block = [f"### {name}", "```python", content[:300]]
            if len(content) > 300:
                block.append("# ... (truncated)")
            block.append("```")
            similar.append("\n".join(block))

    parts = [
        "# Code Generation Task",
        f"**Goal:** Implement `{symbol}` in `{file}`",
        f"**Task type:** {task}",
        "",
    ]
    if deps:
        parts += ["## Available Dependencies", "\n".join(deps[:5]), ""]
    if similar:
        parts += ["## Similar Implementations", "\n".join(similar[:2]), ""]
    if existing_code:
        parts += ["## Existing Code", f"```python\n{existing_code[:400]}\n```", ""]
    parts += [
        "## Code to Generate",
        f"Symbol: `{symbol}`",
        f"Target file: `{file}`",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Format output
# ---------------------------------------------------------------------------
def format_item_source(item: dict) -> str:
    source = item.get("source", "unknown")
    score = item.get("score")
    labels = {
        "qdrant": f"🔍 vector search / Qdrant{f' (score: {score:.2f})' if score else ''}",
        "db_query": "🗄️  DB lookup (direct / graph)",
        "builtin_ast": "📄 AST force-add (target file)",
        "db_direct": "🗄️  DB direct lookup",
        "db_graph": "🕸️  DB graph traversal",
        "vector_search": f"🔍 vector search{f' (score: {score:.2f})' if score else ''}",
    }
    return labels.get(source, f"❓ {source}")


def format_eval_report(
    test_case: dict,
    packet: dict,
    eval_result: dict,
) -> str:
    lines = []
    items = packet.get("context", [])

    lines.append(f"\n{'=' * 80}")
    lines.append(f"TEST CASE: {test_case['name']}")
    lines.append(f"{'=' * 80}")
    lines.append(f"File  : {test_case['file']}")
    lines.append(f"Symbol: {test_case['symbol']}")
    lines.append(f"Task  : {test_case['task']}")
    lines.append("")

    # Evaluation results
    lines.append("## EVALUATION")
    lines.append(f"Score  : {eval_result['score']}")
    lines.append(f"Overall: {eval_result['overall']}")
    lines.append(f"Items  : {eval_result['item_count']}")
    lines.append(f"Tokens : ~{eval_result['tokens_est']}")
    lines.append(f"Time   : {eval_result['duration_ms']}ms")
    lines.append("")
    for check_name, check in eval_result["checks"].items():
        icon = "✅" if check["pass"] else "❌"
        lines.append(f"  {icon} {check_name}: {check['detail']}")
    lines.append("")

    # Context items
    lines.append("## CONTEXT ITEMS")
    lines.append("")
    for idx, item in enumerate(items, 1):
        name = item.get("name", "unknown")
        path = item.get("path", "unknown")
        item_type = item.get("item_type", "?")
        content = item.get("content", "")
        summary = item.get("summary", "")
        source_label = format_item_source(item)

        lines.append(f"### {idx}. {path}::{name}")
        lines.append(f"Type  : {item_type}")
        lines.append(f"Source: {source_label}")
        if summary:
            lines.append(f"Summary: {summary[:100]}")
        if content:
            lines.append("```python")
            lines.append(content[:600])
            if len(content) > 600:
                lines.append("# ... (truncated)")
            lines.append("```")
        else:
            lines.append("(no content)")
        lines.append("")

    # Assembled prompt
    lines.append("## ASSEMBLED PROMPT (what LLM receives)")
    lines.append("")
    prompt = assemble_prompt(
        items, test_case["file"], test_case["symbol"], test_case["task"]
    )
    lines.append(prompt)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
async def run_evaluation() -> None:
    from body.infrastructure.bootstrap import create_core_context
    from body.services.service_registry import service_registry
    from shared.infrastructure.database.session_manager import get_session

    service_registry.prime(get_session)
    core_context = create_core_context(service_registry)

    # Wake up cognitive service for vector search
    async with service_registry.session() as session:
        cognitive = await service_registry.get_cognitive_service()
        await cognitive.initialize(session)

    output_lines = [
        "# CORE Context Build — Evaluation Report",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "This report evaluates whether `core-admin context build` correctly assembles",
        "context packets using the same pipeline as CoderAgent.",
        "",
        "Paste this file to Claude for evaluation.",
        "",
    ]

    all_results = []

    for tc in TEST_CASES:
        print(f"\n⏳ Running: {tc['name']} ...")

        task_spec = {
            "task_id": f"eval_{uuid.uuid4().hex[:8]}",
            "task_type": tc["task"],
            "target_file": tc["file"],
            "target_symbol": tc["symbol"],
            "summary": tc["goal"],
            "scope": {
                "traversal_depth": 2,
                "include": [tc["file"]],
            },
            "constraints": {
                "max_tokens": 30000,
                "max_items": 20,
            },
        }

        try:
            packet = await core_context.context_service.build_for_task(
                task_spec, use_cache=False
            )
            eval_result = evaluate_packet(packet, tc["file"], tc["symbol"], tc["task"])
            report_section = format_eval_report(tc, packet, eval_result)
            output_lines.append(report_section)
            all_results.append(
                (tc["name"], eval_result["overall"], eval_result["score"])
            )
            print(f"   {eval_result['overall']} ({eval_result['score']})")

        except Exception as e:
            output_lines.append(f"\n## ERROR: {tc['name']}\n```\n{e}\n```\n")
            all_results.append((tc["name"], "ERROR", "0/5"))
            print(f"   ERROR: {e}")

    # Summary
    output_lines.append("\n" + "=" * 80)
    output_lines.append("SUMMARY")
    output_lines.append("=" * 80)
    for name, overall, score in all_results:
        icon = "✅" if overall == "PASS" else "⚠️ " if overall == "PARTIAL" else "❌"
        output_lines.append(f"{icon} {name}: {overall} ({score})")

    # Write output
    out_path = Path("var/eval_context_build.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(output_lines), encoding="utf-8")

    print(f"\n✅ Evaluation written to: {out_path}")
    print("   Paste that file to Claude for evaluation.\n")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
