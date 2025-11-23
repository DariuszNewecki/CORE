# src/features/self_healing/capability_tagging_service.py

"""
Service logic for applying capability tags to untagged public symbols
via the CapabilityTaggerAgent.

This module is part of the FEATURES layer and therefore MUST NOT import
from body.cli.* or other higher layers.

Dependencies (ContextService, session factory, cognitive/knowledge services)
must be injected by the caller (CLI or fix workflow).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console
from sqlalchemy import text

from services.knowledge.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger
from will.agents.tagger_agent import CapabilityTaggerAgent
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)
console = Console()
REPO_ROOT = settings.REPO_PATH

# Async DB session factory type
SessionFactory = Callable[[], Any]


async def _async_tag_capabilities(
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    session_factory: SessionFactory,
    file_path: Path | None,
    dry_run: bool,
) -> None:
    """
    Core async logic for capability tagging.

    This function applies new capability IDs to source code and registers them
    in the DB using the injected session_factory. No CLI-layer imports allowed.
    """

    agent = CapabilityTaggerAgent(cognitive_service, knowledge_service)

    suggestions = await agent.suggest_and_apply_tags(
        file_path=file_path.as_posix() if file_path else None
    )

    if not suggestions:
        console.print(
            "[bold green]No new public capabilities to register.[/bold green]"
        )
        return

    # DRY RUN
    if dry_run:
        console.print(
            "[bold yellow]-- DRY RUN: Would apply the following capability tags --[/bold yellow]"
        )
        for key, info in suggestions.items():
            temp_uuid = str(uuid.uuid4())
            console.print(
                f"  • {info['suggestion']} (ID: {temp_uuid}) → "
                f"{info['file']}:{info['line_number']}"
            )
        return

    console.print(
        f"\n[bold green]Applying {len(suggestions)} new capability tags "
        f"to source code...[/bold green]"
    )

    # ------------- DB OPERATION THROUGH INJECTED SESSION ---------------- #
    async with session_factory() as session:
        async with session.begin():
            for _, new_info in suggestions.items():
                suggested_name = new_info["suggestion"]

                # Real UUID for the new capability
                symbol_uuid = str(uuid.uuid4())

                # Convert module path to file system path if needed
                file_path_str = new_info["file"]
                if not file_path_str.endswith(".py"):
                    file_path_str = "src/" + file_path_str.replace(".", "/") + ".py"

                source_file_path = REPO_ROOT / file_path_str

                if not source_file_path.exists():
                    logger.error(f"File not found: {source_file_path}")
                    continue

                # ---------------- Insert tag into code ----------------- #
                lines = source_file_path.read_text("utf-8").splitlines()
                line_to_tag = new_info["line_number"] - 1

                if line_to_tag >= len(lines):
                    logger.error(
                        f"Line {line_to_tag} out of bounds for {source_file_path}"
                    )
                    continue

                original_line = lines[line_to_tag]
                indentation = len(original_line) - len(original_line.lstrip(" "))
                tag_line = f"{' ' * indentation}# ID: {symbol_uuid}"

                lines.insert(line_to_tag, tag_line)
                source_file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

                # ---------------- Register in DB ----------------------- #
                domain = (
                    suggested_name.split(".")[0] if "." in suggested_name else "general"
                )

                upsert_sql = text(
                    """
                    INSERT INTO core.capabilities
                        (name, domain, title, owner, entry_points, status, tags)
                    VALUES
                        (:name, :domain, :name, 'system', ARRAY[:uuid]::uuid[],
                         'Active', '[]'::jsonb)
                    ON CONFLICT (domain, name)
                    DO UPDATE SET
                        entry_points = CASE
                            WHEN NOT (:uuid = ANY(core.capabilities.entry_points))
                            THEN array_append(core.capabilities.entry_points, :uuid)
                            ELSE core.capabilities.entry_points
                        END,
                        updated_at = now();
                    """
                )

                await session.execute(
                    upsert_sql,
                    {"name": suggested_name, "domain": domain, "uuid": symbol_uuid},
                )

                console.print(
                    f"   → Tagged '{suggested_name}' "
                    f"(ID: {symbol_uuid}) in "
                    f"{source_file_path.relative_to(REPO_ROOT)}"
                )

        await session.commit()


# ------------------------------------------------------------------------------
# EXTERNAL PUBLIC ENTRYPOINTS — used by CLI / fix workflows
# ------------------------------------------------------------------------------


# ID: 7216f125-bffe-4e4a-9d0a-2596e9e864bb
def main_sync(
    session_factory: SessionFactory,
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    write: bool = False,
    dry_run: bool = False,
) -> None:
    """Synchronous wrapper for capability tagging."""
    effective_dry_run = dry_run or not write

    asyncio.run(
        _async_tag_capabilities(
            cognitive_service=cognitive_service,
            knowledge_service=knowledge_service,
            session_factory=session_factory,
            file_path=None,
            dry_run=effective_dry_run,
        )
    )


# ID: 528c806f-ba48-4153-8864-7c1ff270e710
async def main_async(
    session_factory: SessionFactory,
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    write: bool = False,
    dry_run: bool = False,
) -> None:
    """Async wrapper used by `fix all` workflows."""
    effective_dry_run = dry_run or not write

    await _async_tag_capabilities(
        cognitive_service=cognitive_service,
        knowledge_service=knowledge_service,
        session_factory=session_factory,
        file_path=None,
        dry_run=effective_dry_run,
    )
