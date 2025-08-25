# src/system/admin/fixer.py
"""
Registers all self-healing and code quality improvement commands for the CORE Admin CLI.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

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
    file_path: Optional[Path] = typer.Argument(
        None,
        help="Optional: The path to a specific file to fix. If omitted, all project files are scanned.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--write", help="Show changes without writing files."
    ),
):
    """
    A unified tool to enforce all constitutional header conventions on Python files.
    """
    files_to_process = []
    if file_path:
        # If a specific file is provided, process only that one.
        log.info(f"🎯 Targeting a single file for header fixing: {file_path}")
        files_to_process.append(str(file_path.relative_to(REPO_ROOT)))
    else:
        # If no file is provided, scan the entire project.
        log.info("🧠 Rebuilding knowledge graph for a complete file list...")
        builder = KnowledgeGraphBuilder(REPO_ROOT)
        graph = builder.build()

        files_to_process = sorted(
            list(
                {
                    s["file"]
                    for s in graph.get("symbols", {}).values()
                    if s.get("file", "").endswith(".py")
                }
            )
        )

    asyncio.run(_run_header_fix_cycle(dry_run, files_to_process))

    if not dry_run:
        log.info("🧠 Rebuilding knowledge graph to reflect all changes...")
        builder = KnowledgeGraphBuilder(REPO_ROOT)
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
