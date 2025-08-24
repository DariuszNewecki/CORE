# src/system/admin/fixer.py
"""
Registers all self-healing and code quality improvement commands for the CORE Admin CLI.
"""
from __future__ import annotations

import asyncio
import json

import typer

from shared.logger import getLogger
from shared.path_utils import get_repo_root
from system.admin.fixer_complexity import complexity_outliers
from system.admin.fixer_header import _run_header_fix_cycle
from system.tools.codegraph_builder import KnowledgeGraphBuilder

log = getLogger("core_admin.fixer")
REPO_ROOT = get_repo_root()
KNOWLEDGE_GRAPH_PATH = REPO_ROOT / ".intent" / "knowledge" / "knowledge_graph.json"


# CAPABILITY: fix.headers
def fix_headers(
    dry_run: bool = typer.Option(
        True, "--dry-run/--write", help="Show changes without writing files."
    )
):
    """
    A unified tool to enforce all constitutional header conventions on Python files.
    """
    log.info("🧠 Rebuilding knowledge graph for a complete file list...")
    builder = KnowledgeGraphBuilder(REPO_ROOT)
    graph = builder.build()

    all_py_files = sorted(
        list(
            {
                s["file"]
                for s in graph.get("symbols", {}).values()
                if s.get("file", "").endswith(".py")
            }
        )
    )

    # THIS IS THE FIX: We no longer pass cognitive_service here.
    asyncio.run(_run_header_fix_cycle(dry_run, all_py_files))

    if not dry_run:
        log.info("🧠 Rebuilding knowledge graph to reflect all changes...")
        graph = builder.build()
        KNOWLEDGE_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        log.info("✅ Knowledge graph successfully updated.")


def register(app: typer.Typer) -> None:
    """Intent: Register fixer commands under the admin CLI."""
    fixer_app = typer.Typer(
        help="Self-healing and code quality tools that enforce constitutional style."
    )
    app.add_typer(fixer_app, name="fix")

    fixer_app.command("headers")(fix_headers)
    fixer_app.command("complexity-outliers")(complexity_outliers)
