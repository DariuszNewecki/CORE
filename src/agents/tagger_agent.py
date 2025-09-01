# src/agents/tagger_agent.py
"""
Implements the CapabilityTaggerAgent, which finds unassigned capabilities
and uses an LLM to suggest constitutionally-valid names for them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.table import Table

from core.cognitive_service import CognitiveService
from core.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor

log = getLogger("tagger_agent")


# CAPABILITY: agent.capability_tagger
class CapabilityTaggerAgent:
    """An agent that finds unassigned capabilities and suggests names."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        knowledge_service: KnowledgeService,
    ):
        """Initializes the agent with the tools it needs."""
        self.cognitive_service = cognitive_service
        self.knowledge_service = knowledge_service
        self.console = Console()
        prompt_path = settings.MIND / "prompts" / "capability_tagger.prompt"
        self.prompt_template = prompt_path.read_text(encoding="utf-8")
        self.existing_capabilities = self.knowledge_service.list_capabilities()
        self.tagger_client = self.cognitive_service.get_client_for_role("CodeReviewer")

    # CAPABILITY: agent.capability_tagger.suggest_and_apply
    async def _get_suggestion_for_symbol(
        self, symbol: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Async worker to get a single tag suggestion from the LLM."""
        symbol_info = {
            "key": symbol.get("key"),
            "name": symbol.get("name"),
            "file": symbol.get("file"),
            "domain": symbol.get("domain"),
            "docstring": symbol.get("docstring"),
        }
        final_prompt = self.prompt_template.format(
            existing_capabilities=json.dumps(self.existing_capabilities, indent=2),
            symbol_info=json.dumps(symbol_info, indent=2),
        )
        response = await self.tagger_client.make_request_async(
            final_prompt, user_id="tagger_agent"
        )
        try:
            suggestion = json.loads(response).get("suggested_capability")
            if suggestion:
                return {
                    "key": symbol["key"],
                    "name": symbol["name"],
                    "file": symbol["file"],
                    "suggestion": suggestion,
                }
        except (json.JSONDecodeError, AttributeError):
            log.warning(f"Could not parse suggestion for {symbol['name']}.")
        return None

    def suggest_and_apply_tags(
        self, file_path: Path | None = None, write_changes: bool = False
    ):
        """Finds unassigned symbols and orchestrates suggesting and applying tags."""
        log.info("🔍 Searching for unassigned capabilities...")
        all_unassigned = [
            s
            for s in self.knowledge_service.graph.get("symbols", {}).values()
            if s.get("capability") == "unassigned"
        ]
        target_symbols = [
            s
            for s in all_unassigned
            if not file_path or s.get("file") == str(file_path)
        ]

        if not target_symbols:
            log.info("✅ No unassigned capabilities found for the given scope.")
            return

        log.info(f"Found {len(target_symbols)} unassigned symbols. Analyzing...")

        # Use the new ThrottledParallelProcessor
        processor = ThrottledParallelProcessor(description="Analyzing symbols...")
        results = processor.run(target_symbols, self._get_suggestion_for_symbol)

        # Process the results
        suggestions_to_apply = {}
        table = Table(title="🤖 Capability Tagger Agent Suggestions")
        table.add_column("Symbol", style="cyan")
        table.add_column("File", style="green")
        table.add_column("Suggested Capability", style="yellow")
        for res in filter(None, results):
            table.add_row(res["name"], res["file"], res["suggestion"])
            suggestions_to_apply[res["key"]] = res["suggestion"]

        self.console.print(table)

        if write_changes:
            log.info("💾 Applying suggested tags to files...")
            self._apply_tags_to_files(suggestions_to_apply)
        else:
            log.info("💧 Dry Run complete. No files were modified.")

    def _apply_tags_to_files(self, suggestions: dict[str, str]):
        """
        Applies the suggested capability tags to the relevant source code files.

        This method groups suggestions by file, reads each file, inserts the
        new capability tags on the line above the symbol definition, and
        writes the modified content back to disk.
        """
        files_to_modify = {}
        for key, new_tag in suggestions.items():
            file_str, symbol_name = key.split("::")
            if file_str not in files_to_modify:
                files_to_modify[file_str] = []
            files_to_modify[file_str].append((symbol_name, new_tag))

        for file_str, tags_to_add in files_to_modify.items():
            try:
                # CAPABILITY: agent.capability_tagger.apply_tags_to_files
                p = settings.REPO_PATH / file_str
                content = p.read_text(encoding="utf-8")
                lines = content.splitlines()
                tags_to_add.sort(
                    key=lambda x: self.knowledge_service.graph["symbols"][
                        f"{file_str}::{x[0]}"
                    ]["line_number"],
                    reverse=True,
                )
                for symbol_name, new_tag in tags_to_add:
                    symbol_data = self.knowledge_service.graph["symbols"][
                        f"{file_str}::{symbol_name}"
                    ]
                    line_num = symbol_data["line_number"]
                    original_line = lines[line_num - 1]
                    indentation = len(original_line) - len(original_line.lstrip(" "))
                    lines.insert(
                        line_num - 1, f"{' ' * indentation}# CAPABILITY: {new_tag}"
                    )
                p.write_text("\n".join(lines), encoding="utf-8")
                log.info(f"   -> ✅ Wrote {len(tags_to_add)} tag(s) to {file_str}")
            except Exception as e:
                log.error(f"   -> ❌ Failed to write tags to {file_str}: {e}")
