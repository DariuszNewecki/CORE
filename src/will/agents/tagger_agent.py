# src/will/agents/tagger_agent.py

"""
Implements the CapabilityTaggerAgent, which finds unassigned capabilities
and uses an LLM to suggest constitutionally-valid names for them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from services.knowledge.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: fa3e820c-ed8c-4785-b94d-4cb5a1ae23b8
class CapabilityTaggerAgent:
    """An agent that finds unassigned capabilities and suggests names."""

    def __init__(
        self, cognitive_service: CognitiveService, knowledge_service: KnowledgeService
    ):
        """Initializes the agent with the tools it needs."""
        self.cognitive_service = cognitive_service
        self.knowledge_service = knowledge_service
        self.console = Console()
        prompt_path = settings.MIND / "mind" / "prompts" / "capability_definer.prompt"
        self.prompt_template = prompt_path.read_text(encoding="utf-8")
        self.tagger_client = None

        # Load entry point patterns (same as OrphanedLogicCheck)
        self.entry_point_patterns = settings.load(
            "mind.knowledge.project_structure"
        ).get("entry_point_patterns", [])

    def _is_entry_point(self, symbol_data: dict[str, Any]) -> bool:
        """
        Checks if a symbol matches any of the defined entry point patterns.
        Copied directly from OrphanedLogicCheck.
        """
        for pattern in self.entry_point_patterns:
            match_rules = pattern.get("match", {})
            if not match_rules:
                continue
            is_a_match = all(
                self._evaluate_match_rule(rule_key, rule_value, symbol_data)
                for rule_key, rule_value in match_rules.items()
            )
            if is_a_match:
                return True
        return False

    def _evaluate_match_rule(self, key: str, value: Any, data: dict) -> bool:
        """
        Evaluates a single criterion for the entry point pattern matching.
        Copied directly from OrphanedLogicCheck.
        """
        if key == "type":
            kind = data.get("type", "")
            is_function_type = kind in ("function", "method")
            return (value == "function" and is_function_type) or (value == kind)
        if key == "name_regex":
            return bool(re.search(value, data.get("name", "")))
        if key == "module_path_contains":
            file_path = data.get("file_path", "")
            module_path = (
                file_path.replace("src/", "").replace(".py", "").replace("/", ".")
            )
            return value in module_path
        if key == "is_public_function":
            return data.get("is_public", False) is value
        if key == "has_capability_tag":
            return (data.get("capability") is not None) == value
        return data.get(key) == value

    def _find_orphaned_symbols(self, all_symbols: list[dict]) -> list[dict]:
        """
        Finds truly orphaned symbols using the exact same logic as OrphanedLogicCheck.

        A symbol is orphaned if it is:
        1. Public
        2. Has no capability assigned (capability is None)
        3. Is NOT an entry point
        4. Is NOT called by any other code
        """
        if not all_symbols:
            return []

        # Build call graph (same as OrphanedLogicCheck)
        all_called_symbols = set()
        for symbol_data in all_symbols:
            called_list = symbol_data.get("calls") or []
            for called_qualname in called_list:
                all_called_symbols.add(called_qualname)

        # Find orphaned symbols (same logic as OrphanedLogicCheck)
        orphaned_symbols = []
        for symbol_data in all_symbols:
            is_public = symbol_data.get("is_public", False)
            has_no_key = symbol_data.get("capability") is None

            if not (is_public and has_no_key):
                continue

            if self._is_entry_point(symbol_data):
                continue

            qualname = symbol_data.get("name", "")
            short_name = qualname.split(".")[-1]
            is_called = (qualname in all_called_symbols) or (
                short_name in all_called_symbols
            )

            if not is_called:
                orphaned_symbols.append(symbol_data)

        return orphaned_symbols

    async def _get_existing_capabilities(self) -> list[str]:
        """Fetches existing capabilities asynchronously."""
        return await self.knowledge_service.list_capabilities()

    def _extract_symbol_info(self, symbol: dict[str, Any]) -> dict[str, Any]:
        """Extracts the relevant information for the prompt from a symbol entry."""
        return {
            "key": symbol.get("uuid"),
            "name": symbol.get("name"),
            "file": symbol.get("file_path"),
            "domain": symbol.get("domain"),
            "docstring": symbol.get("docstring"),
        }

    def _build_suggestion_prompt(
        self, symbol_info: dict[str, Any], existing_capabilities: list[str]
    ) -> str:
        """Builds the final prompt for AI suggestion request."""
        # Format existing capabilities as "similar capabilities" context
        similar_caps_text = "\n".join(
            [f"- {cap}" for cap in existing_capabilities[:20]]
        )

        # Build code snippet from symbol info
        code_snippet = f"# {symbol_info.get('name', 'unknown')}\n"
        if symbol_info.get("docstring"):
            code_snippet += f'"""{symbol_info["docstring"]}"""\n'
        code_snippet += f"# Domain: {symbol_info.get('domain', 'unknown')}\n"
        code_snippet += f"# File: {symbol_info.get('file', 'unknown')}"

        return self.prompt_template.format(
            similar_capabilities=similar_caps_text,
            code=code_snippet,
        )

    async def _get_suggestion_for_symbol(
        self, symbol: dict[str, Any], existing_capabilities: list[str]
    ) -> dict[str, str] | None:
        """Async worker to get a single tag suggestion from the LLM."""
        symbol_info = self._extract_symbol_info(symbol)
        final_prompt = self._build_suggestion_prompt(symbol_info, existing_capabilities)
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
                    "key": symbol["uuid"],
                    "name": symbol["name"],
                    "file": symbol["file_path"],
                    "line_number": symbol.get("line_number", 1),
                    "suggestion": suggestion,
                }
        except (json.JSONDecodeError, AttributeError):
            logger.warning(f"Could not parse suggestion for {symbol['name']}.")
        return None

    # ID: 31b9d32d-7a97-44cb-8472-1e46f4c1ee99
    async def suggest_and_apply_tags(
        self, file_path: Path | None = None
    ) -> dict[str, dict] | None:
        """
        Finds truly orphaned public symbols (using OrphanedLogicCheck logic),
        gets AI-powered suggestions, and returns them.
        """
        if self.tagger_client is None:
            self.tagger_client = await self.cognitive_service.aget_client_for_role(
                "CodeReviewer"
            )

        logger.info("🔍 Searching for orphaned capabilities (using audit logic)...")

        existing_capabilities = await self._get_existing_capabilities()
        graph = await self.knowledge_service.get_graph()
        all_symbols = list(graph.get("symbols", {}).values())

        # Use the same orphan detection logic as OrphanedLogicCheck
        orphaned_symbols = self._find_orphaned_symbols(all_symbols)

        logger.info(
            f"   -> Found {len(orphaned_symbols)} truly orphaned symbols (same as audit)."
        )

        # Filter by file_path if specified
        target_symbols = [
            s
            for s in orphaned_symbols
            if not file_path or s.get("file_path") == str(file_path)
        ]

        if not target_symbols:
            return None

        logger.info(
            f"Analyzing {len(target_symbols)} orphaned symbols for capability suggestions..."
        )
        processor = ThrottledParallelProcessor(description="Analyzing symbols...")
        results = await processor.run_async(
            target_symbols,
            lambda symbol: self._get_suggestion_for_symbol(
                symbol, existing_capabilities
            ),
        )
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
