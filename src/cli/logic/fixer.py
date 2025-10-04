# src/cli/logic/fixer.py
"""
Registers all self-healing and code quality improvement commands that WRITE changes
to the codebase or constitution. This is the single entry point for all 'fix' commands.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from core.agents.tagger_agent import CapabilityTaggerAgent
from core.cognitive_service import CognitiveService
from core.knowledge_service import KnowledgeService
from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from features.self_healing.clarity_service import fix_clarity
from features.self_healing.complexity_service import complexity_outliers
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.header_service import _run_header_fix_cycle
from features.self_healing.id_tagging_service import assign_missing_ids
from features.self_healing.linelength_service import fix_line_lengths
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


fix_app = typer.Typer(
    help="Self-healing tools that write changes to fix constitutional violations."
)


@fix_app.command(
    "format", help="Auto-format all code to be constitutionally compliant."
)
# ID: ac0d6bc3-83d5-44c4-8755-222205b77f15
def format_code_wrapper():
    """Format all code in the `src` and `tests` directories using Black and Ruff with automatic fixes."""
    _run_poetry_command("✨ Formatting code with Black...", ["black", "src", "tests"])
    _run_poetry_command(
        "✨ Fixing code with Ruff...", ["ruff", "check", "src", "tests", "--fix"]
    )


@fix_app.command(
    "headers",
    help="Enforces constitutional header conventions on Python files.",
)
# ID: 51be431e-c7b4-4b76-8c32-bd6ce9acad9f
def fix_headers_cmd(
    file_path: Optional[Path] = typer.Argument(
        None,
        help="Optional: A specific file to fix. If omitted, all project files are scanned.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
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


@fix_app.command(
    "tags",
    help="Finds unassigned capabilities and registers them in the database.",
)
# ID: 05d13ed4-367f-4ac8-a611-730798157b8c
def fix_tags_cmd_wrapper(
    file_path: Optional[Path] = typer.Argument(
        None, help="Optional: Path to a specific file."
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the suggested tags to files and DB."
    ),
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


fix_app.command(
    "orphaned-vectors", help="Finds and deletes orphaned vectors from Qdrant."
)(prune_orphaned_vectors)
fix_app.command(
    "private-capabilities", help="Removes #CAPABILITY tags from private symbols."
)(prune_private_capabilities)
fix_app.command("complexity", help="Identifies and refactors complexity outliers.")(
    complexity_outliers
)
fix_app.command("line-lengths", help="Refactors files with long lines.")(
    fix_line_lengths
)
fix_app.command("docstrings", help="Adds missing docstrings.")(fix_docstrings)
fix_app.command("clarity", help="Refactors a file for clarity.")(fix_clarity)


@fix_app.command(
    "purge-legacy-tags", help="Finds and removes all obsolete '# CAPABILITY:' tags."
)
# ID: 14aa94ca-ab55-4a91-9507-ca959a894a18
def purge_legacy_tags_command(
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply the changes and permanently delete the legacy tags.",
    ),
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
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin knowledge sync --write' to update the database."
        )


@fix_app.command(
    "assign-ids", help="Assigns a stable '# ID: <uuid>' to all untagged public symbols."
)
# ID: 103780db-c852-4026-a296-3e1c68e19246
def assign_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes and add new ID tags to source files."
    ),
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
        # --- THIS IS THE FIX ---
        # Updated the command to the new, correct one.
        console.print(
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin manage database sync-knowledge --write' to update the database."
        )
        # --- END OF FIX ---


@fix_app.command(
    "policy-ids", help="Adds a UUID to all policy files that are missing one."
)
# ID: 81a2b3c4-d5e6-f7a8-b9c0-d1e2f3a4b5c6
def fix_policy_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes and add new IDs to policy files."
    ),
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
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin check ci audit' to verify constitutional compliance."
        )


# ID: a119b740-e2ef-4386-9ef1-ac607e4128e2
def register(app: typer.Typer):
    """Register the consolidated 'fix' command group with the main CLI app."""
    app.add_typer(fix_app, name="fix")
