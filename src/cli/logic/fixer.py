# src/cli/logic/fixer.py
"""
Contains the business logic for all self-healing and code quality improvement commands.
This is a pure logic module, with no CLI definitions.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from core.agents.tagger_agent import CapabilityTaggerAgent
from core.cognitive_service import CognitiveService
from core.knowledge_service import KnowledgeService
from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from features.self_healing.clarity_service import fix_clarity as clarity_logic
from features.self_healing.complexity_service import (
    complexity_outliers as complexity_logic,
)
from features.self_healing.docstring_service import fix_docstrings as docstrings_logic
from features.self_healing.header_service import _run_header_fix_cycle
from features.self_healing.id_tagging_service import assign_missing_ids
from features.self_healing.linelength_service import (
    fix_line_lengths as linelength_logic,
)
from features.self_healing.policy_id_service import add_missing_policy_ids
from features.self_healing.prune_orphaned_vectors import (
    main_sync as prune_orphaned_vectors,
)
from features.self_healing.prune_private_capabilities import (
    main as prune_private_capabilities,
)
from features.self_healing.purge_legacy_tags_service import purge_legacy_tags
from rich.console import Console
from services.repositories.db.engine import get_session
from shared.config import settings
from shared.logger import getLogger

from .cli_utils import _run_poetry_command

log = getLogger("core_admin.fix")
console = Console()
REPO_ROOT = settings.REPO_PATH


# ID: ac0d6bc3-83d5-44c4-8755-222205b77f15
def format_code_wrapper():
    """Format all code in the `src` and `tests` directories using Black and Ruff with automatic fixes."""
    _run_poetry_command("✨ Formatting code with Black...", ["black", "src", "tests"])
    _run_poetry_command(
        "✨ Fixing code with Ruff...", ["ruff", "check", "src", "tests", "--fix"]
    )


# ID: 51be431e-c7b4-4b76-8c32-bd6ce9acad9f
def fix_headers_cmd(
    file_path: Optional[Path] = None,
    write: bool = False,
):
    """User-friendly wrapper for the header fixing logic."""
    dry_run = not write
    files_to_process = []
    if file_path:
        log.info(f"🎯 Targeting a single file for header fixing: {file_path}")
        files_to_process.append(str(file_path.relative_to(REPO_ROOT)))
    else:
        log.info("Scanning all Python files in the 'src' directory...")
        src_dir = REPO_ROOT / "src"
        all_py_files = src_dir.rglob("*.py")
        files_to_process = sorted([str(p.relative_to(REPO_ROOT)) for p in all_py_files])

    _run_header_fix_cycle(dry_run, files_to_process)

    if not dry_run:
        log.info("🧠 Rebuilding knowledge graph to reflect all changes...")
        builder = KnowledgeGraphBuilder(REPO_ROOT)
        asyncio.run(builder.build_and_sync())
        log.info("✅ Knowledge graph successfully updated.")


# ID: 05d13ed4-367f-4ac8-a611-730798157b8c
def fix_tags_cmd_wrapper(
    file_path: Optional[Path] = None,
    write: bool = False,
):
    """Wrapper for the CapabilityTaggerAgent that writes to the database."""

    async def _async_fix_tags():
        knowledge_service = KnowledgeService(settings.REPO_PATH)
        cognitive_service = CognitiveService(settings.REPO_PATH)
        agent = CapabilityTaggerAgent(cognitive_service, knowledge_service)

        suggestions = await agent.suggest_and_apply_tags(
            file_path=file_path.as_posix() if file_path else None
        )

        if not suggestions:
            console.print(
                "[bold green]✅ No new public capabilities to register.[/bold green]"
            )
            return

        if not write:
            console.print(
                "[bold yellow]💧 Dry Run: Run with --write to register new capabilities.[/bold yellow]"
            )
            return

        console.print(
            f"\n[bold green]✅ Applying {len(suggestions)} new capability tags to source code...[/bold green]"
        )

        async with get_session() as session:
            async with session.begin():
                for key, new_info in suggestions.items():
                    suggested_name = new_info["suggestion"]

                    graph = await knowledge_service.get_graph()
                    source_file_path = REPO_ROOT / new_info["file"]
                    lines = source_file_path.read_text("utf-8").splitlines()
                    symbol_data = graph["symbols"][new_info["key"]]
                    line_to_tag = symbol_data["line_number"] - 1

                    original_line = lines[line_to_tag]
                    indentation = len(original_line) - len(original_line.lstrip(" "))
                    tag_line = f"{' ' * indentation}# ID: {suggested_name}"

                    lines.insert(line_to_tag, tag_line)
                    source_file_path.write_text(
                        "\n".join(lines) + "\n", encoding="utf-8"
                    )
                    console.print(
                        f"   -> Tagged '{suggested_name}' in {new_info['file']}"
                    )

        log.info("🧠 Rebuilding knowledge graph to reflect changes...")
        builder = KnowledgeGraphBuilder(REPO_ROOT)
        await builder.build_and_sync()
        log.info("✅ Knowledge graph successfully updated.")

    asyncio.run(_async_fix_tags())


# Logic functions are aliased or defined for clarity.
fix_orphaned_vectors = prune_orphaned_vectors
fix_private_capabilities = prune_private_capabilities
fix_complexity = complexity_logic
fix_line_lengths = linelength_logic
fix_docstrings = docstrings_logic
fix_clarity = clarity_logic


# ID: 14aa94ca-ab55-4a91-9507-ca959a894a18
def purge_legacy_tags_command(
    write: bool = False,
):
    """
    CLI wrapper for the legacy tag purging service.
    """
    dry_run = not write
    total_removed = purge_legacy_tags(dry_run=dry_run)

    console.print("\n--- Purge Complete ---")
    if dry_run:
        console.print(f"💧 DRY RUN: Found {total_removed} total legacy tags to remove.")
        console.print("   Run with '--write' to apply these changes.")
    else:
        console.print(f"✅ APPLIED: Successfully removed {total_removed} legacy tags.")
        console.print(
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin manage database sync-knowledge --write' to update the database."
        )


# ID: 103780db-c852-4026-a296-3e1c68e19246
def assign_ids_command(
    write: bool = False,
):
    """
    CLI wrapper for the symbol ID tagging service.
    """
    dry_run = not write
    total_assigned = assign_missing_ids(dry_run=dry_run)

    console.print("\n--- ID Assignment Complete ---")
    if total_assigned == 0 and not dry_run:
        console.print("[bold green]✅ No new IDs were needed.[/bold green]")
        return

    if dry_run:
        console.print(
            f"💧 DRY RUN: Found {total_assigned} public symbols that need an ID."
        )
        console.print("   Run with '--write' to apply these changes.")
    else:
        console.print(f"✅ APPLIED: Successfully assigned {total_assigned} new IDs.")
        console.print(
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin manage database sync-knowledge --write' to update the database."
        )


# ID: 81a2b3c4-d5e6-f7a8-b9c0-d1e2f3a4b5c6
def fix_policy_ids_command(
    write: bool = False,
):
    """CLI wrapper for the policy ID migration service."""
    dry_run = not write
    total_updated = add_missing_policy_ids(dry_run=dry_run)

    console.print("\n--- Policy ID Migration Complete ---")
    if dry_run:
        console.print(f"💧 DRY RUN: Found {total_updated} policies that need a UUID.")
        console.print("   Run with '--write' to apply these changes.")
    else:
        console.print(f"✅ APPLIED: Successfully updated {total_updated} policies.")
        console.print(
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin check audit' to verify constitutional compliance."
        )
