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

from shared.ai.prompt_model import PromptModel
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: fa3e820c-ed8c-4785-b94d-4cb5a1ae23b8
class CapabilityTaggerAgent:
    """An agent that finds unassigned capabilities and suggests names."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        knowledge_service: KnowledgeService,
        entry_point_patterns: list | None = None,
    ):
        """Initializes the agent with the tools it needs."""
        self.cognitive_service = cognitive_service
        self.knowledge_service = knowledge_service
        self.tracer = DecisionTracer()
        self.prompt_model = PromptModel.load("capability_definer")
        self.tagger_client = None
        self.entry_point_patterns = entry_point_patterns or []

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

    def _build_prompt_context(
        self, symbol_info: dict[str, Any], existing_capabilities: list[str]
    ) -> dict[str, str]:
        """
        Builds the PromptModel context dict for a single symbol invocation.

        Returns a dict matching the input contract declared in model.yaml.
        """
        similar_caps_text = "\n".join(
            [f"- {cap}" for cap in existing_capabilities[:20]]
        )

        code_snippet = f"# {symbol_info.get('name', 'unknown')}\n"
        if symbol_info.get("docstring"):
            code_snippet += f'"""{symbol_info["docstring"]}"""\n'
        code_snippet += f"# Domain: {symbol_info.get('domain', 'unknown')}\n"
        code_snippet += f"# File: {symbol_info.get('file', 'unknown')}"

        return {
            "similar_capabilities": similar_caps_text,
            "code": code_snippet,
        }

    @staticmethod
    def _strip_markdown(response: str) -> str:
        """Strips markdown code fences from LLM response if present."""
        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-z]*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean.strip())
        return clean.strip()

    async def _get_suggestion_for_symbol(
        self, symbol: dict[str, Any], existing_capabilities: list[str]
    ) -> dict[str, str] | None:
        """
        Async worker to get a single tag suggestion from the LLM via PromptModel.
        """
        symbol_info = self._extract_symbol_info(symbol)
        context = self._build_prompt_context(symbol_info, existing_capabilities)

        try:
            response = await self.prompt_model.invoke(
                context,
                client=self.tagger_client,
                user_id="tagger_agent",
            )
            parsed = json.loads(self._strip_markdown(response))
            suggestion = parsed.get("suggested_capability")

            # DECISION TRACING: record the LLM-driven capability suggestion.
            # Satisfies autonomy.tracing.mandatory by recording the agent's
            # core decision — what capability name to suggest for an
            # orphaned symbol — at the point the LLM response is parsed.
            self.tracer.record(
                agent="CapabilityTaggerAgent",
                decision_type="capability_suggestion",
                rationale=(
                    f"LLM produced suggestion for orphaned symbol "
                    f"{symbol.get('name')!r} in {symbol_info.get('file')!r}"
                ),
                chosen_action=(
                    f"Suggest capability: {suggestion!r}"
                    if suggestion
                    else "Reject — LLM returned no suggestion"
                ),
                alternatives=existing_capabilities[:5],
                context={
                    "symbol_uuid": symbol.get("uuid"),
                    "symbol_name": symbol.get("name"),
                    "file": symbol_info.get("file"),
                    "domain": symbol_info.get("domain"),
                },
                confidence=0.8 if suggestion else 0.0,
            )

            if not suggestion:
                return None
            return {
                "key": symbol.get("uuid"),
                "name": symbol.get("name"),
                "file": symbol_info.get("file"),
                "line_number": symbol.get("line_number", 1),
                "suggestion": suggestion,
            }
        except (json.JSONDecodeError, AttributeError, ValueError):
            logger.warning("Could not parse suggestion for %s.", symbol.get("name"))
        return None

    # ID: 02466161-a46e-4fc2-8011-ddd05ada4d1c
    async def suggest_and_apply_tags(
        self,
        file_path: Path | None = None,
        limit: int = 0,
    ) -> dict[str, dict] | None:
        """
        Finds truly orphaned public symbols (using OrphanedLogicCheck logic),
        gets AI-powered suggestions via PromptModel, and returns them.

        Args:
            file_path: Optional path to filter symbols by file.
            limit: Max number of symbols to process (0 = all).

        Returns:
            Dict mapping symbol keys to suggestion dicts, or None if no suggestions.
        """
        if self.tagger_client is None:
            self.tagger_client = await self.cognitive_service.aget_client_for_role(
                self.prompt_model.manifest.role
            )

        logger.info("Searching for orphaned capabilities (using audit logic)...")

        existing_capabilities = await self._get_existing_capabilities()
        graph = await self.knowledge_service.get_graph()
        all_symbols = list(graph.get("symbols", {}).values())

        orphaned_symbols = self._find_orphaned_symbols(all_symbols)

        if file_path:
            orphaned_symbols = [
                s
                for s in orphaned_symbols
                if s.get("file_path", "").endswith(str(file_path))
            ]

        if limit > 0:
            orphaned_symbols = orphaned_symbols[:limit]

        logger.info(
            "Found %d truly orphaned symbols (same as audit).", len(orphaned_symbols)
        )

        if not orphaned_symbols:
            return None

        logger.info(
            "Analyzing %d orphaned symbols for capability suggestions...",
            len(orphaned_symbols),
        )

        processor = ThrottledParallelProcessor(description="Tagging capabilities...")

        # ID: 00304bca-a84a-499c-b6ce-124cf6c24ad9
        async def worker_fn(symbol: dict) -> dict | None:
            return await self._get_suggestion_for_symbol(symbol, existing_capabilities)

        results = await processor.run_async(
            items=orphaned_symbols,
            worker_fn=worker_fn,
        )

        suggestions = {r["key"]: r for r in results if r is not None}

        return suggestions or None
