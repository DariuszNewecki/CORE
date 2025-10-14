# src/features/self_healing/capability_tagging_service.py
"""
Provides the service logic for using an AI agent to suggest and apply
capability tags to untagged public symbols in the codebase.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console

from core.agents.tagger_agent import CapabilityTaggerAgent
from core.cognitive_service import CognitiveService
from core.knowledge_service import KnowledgeService
from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger

log = getLogger("capability_tagging_service")
console = Console()
REPO_ROOT = settings.REPO_PATH


async def _async_tag_capabilities(
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    file_path: Path | None,
    write: bool,
):
    """The core async logic for the capability tagging process."""
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
            "[bold yellow]💧 Dry Run: Run with --write to apply suggested capability tags.[/bold yellow]"
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
                source_file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                console.print(f"   -> Tagged '{suggested_name}' in {new_info['file']}")

    log.info("🧠 Rebuilding knowledge graph to reflect changes...")
    builder = KnowledgeGraphBuilder(REPO_ROOT)
    await builder.build_and_sync()
    log.info("✅ Knowledge graph successfully updated.")


# ID: 1651d1d3-f58c-4fce-8662-c9591c70edf7
def tag_unassigned_capabilities(
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    file_path: Path | None,
    write: bool,
):
    """Synchronous wrapper for the capability tagging service."""
    asyncio.run(
        _async_tag_capabilities(cognitive_service, knowledge_service, file_path, write)
    )
