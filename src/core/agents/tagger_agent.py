# src/agents/tagger_agent.py
"""
Implements the CapabilityTaggerAgent, which finds unassigned capabilities
and uses an LLM to suggest constitutionally-valid names for them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from core.cognitive_service import CognitiveService
from core.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor

log = getLogger("tagger_agent")


# ID: 444b630b-9cf5-4e70-ad60-4756e34144e8
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

    def _extract_symbol_info(self, symbol: dict[str, Any]) -> dict[str, Any]:
        """Extracts the relevant information for the prompt from a symbol entry."""
        return {
            "key": symbol.get("key"),
            "name": symbol.get("name"),
            "file": symbol.get("file"),
            "domain": symbol.get("domain"),
            "docstring": symbol.get("docstring"),
        }

    def _build_suggestion_prompt(self, symbol_info: dict[str, Any]) -> str:
        """Builds the final prompt for AI suggestion request."""
        return self.prompt_template.format(
            existing_capabilities=json.dumps(self.existing_capabilities, indent=2),
            symbol_info=json.dumps(symbol_info, indent=2),
        )

    async def _get_suggestion_for_symbol(
        self, symbol: dict[str, Any]
    ) -> dict[str, str] | None:
        """Async worker to get a single tag suggestion from the LLM."""
        symbol_info = self._extract_symbol_info(symbol)
        final_prompt = self._build_suggestion_prompt(symbol_info)
        response = await self.tagger_client.make_request_async(
            final_prompt, user_id="tagger_agent"
        )
        try:
            parsed = json.loads(response)
            suggestion = parsed.get("suggested_capability")

            if suggestion is None:
                return None

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

    # ID: 4c92bdd4-66f8-4292-b9c4-daeb2d7fdff7
    async def suggest_and_apply_tags(
        self, file_path: Path | None = None
    ) -> dict[str, dict] | None:
        """
        Finds unassigned public symbols, gets AI-powered suggestions, and returns them.
        """
        log.info("🔍 Searching for unassigned capabilities...")
        all_unassigned = [
            s
            for s in self.knowledge_service.graph.get("symbols", {}).values()
            if s.get("capability") == "unassigned"
        ]
        public_unassigned_symbols = [
            s for s in all_unassigned if not s.get("name", "").startswith("_")
        ]
        log.info(
            f"   -> Filtering to {len(public_unassigned_symbols)} public symbols for AI analysis."
        )

        target_symbols = [
            s
            for s in public_unassigned_symbols
            if not file_path or s.get("file") == str(file_path)
        ]

        if not target_symbols:
            return None

        log.info(f"Found {len(target_symbols)} unassigned public symbols. Analyzing...")

        processor = ThrottledParallelProcessor(description="Analyzing symbols...")
        # --- THIS IS THE KEY LINE ---
        results = await processor.run_async(
            target_symbols, self._get_suggestion_for_symbol
        )
        # --- END KEY LINE ---

        suggestions_to_return = {}
        table = Table(title="🤖 Capability Tagger Agent Suggestions")
        table.add_column("Symbol", style="cyan")
        table.add_column("File", style="green")
        table.add_column("Suggested Capability", style="yellow")

        valid_results = filter(None, results)
        for res in valid_results:
            table.add_row(res["name"], res["file"], res["suggestion"])
            suggestions_to_return[res["key"]] = res

        if not suggestions_to_return:
            return None

        self.console.print(table)
        return suggestions_to_return
