# src/will/tools/architectural_context_builder.py

"""
Builds rich architectural context for code generation.

FIXED: Added support for test generation with actual file contents.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService
    from will.tools.module_anchor_generator import ModuleAnchorGenerator
    from will.tools.policy_vectorizer import PolicyVectorizer

logger = getLogger(__name__)


def _read_file_lines_sync(path: Path) -> list[str]:
    """Synchronous file reading helper."""
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


# ID: 2b8c9d4a-1e3f-4d5b-9c6a-7e8f9a0b1c2d
@dataclass
# ID: 5a520778-2e61-4f0b-b3ae-6173d8b0642c
class CodeExample:
    """Example code snippet for reference."""

    file_path: str
    symbol_name: str
    code_snippet: str
    purpose: str
    similarity_score: float


# ID: 4132cf73-dafe-40f7-b15c-54d82dc198ba
@dataclass
# ID: 312a17a7-26b3-4cfc-b892-a85b81c89103
class ArchitecturalContext:
    """Rich context for code generation with A2 enhancements."""

    goal: str
    target_layer: str
    layer_purpose: str
    layer_patterns: list[str]
    relevant_policies: list[dict[str, Any]]
    placement_confidence: str
    best_module_path: str
    placement_score: float
    similar_examples: list[CodeExample] = field(default_factory=list)
    typical_dependencies: list[str] = field(default_factory=list)
    placement_reasoning: str = ""
    common_patterns_in_module: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    # NEW: For test generation
    target_file_content: str | None = None
    target_file_path: str | None = None


# ID: ecbb2cd5-4cdd-42db-9d3f-10663a2c1787
class ArchitecturalContextBuilder:
    """
    Builds rich architectural context for code generation.

    FIXED: Now includes actual file contents for test generation.
    """

    def __init__(
        self,
        policy_vectorizer: PolicyVectorizer,
        anchor_generator: ModuleAnchorGenerator,
        cognitive_service: CognitiveService | None = None,
        qdrant_service: QdrantService | None = None,
    ):
        self.policy_vectorizer = policy_vectorizer
        self.anchor_generator = anchor_generator
        self.cognitive_service = cognitive_service
        self.qdrant_service = qdrant_service
        self.repo_root = settings.REPO_PATH
        logger.info("ArchitecturalContextBuilder (A2 Enhanced) initialized")

    # ID: 30e6b4d7-051a-48e6-b3e4-92e9689d268d
    async def build_context(
        self, goal: str, target_file: str | None = None
    ) -> ArchitecturalContext:
        """
        Build comprehensive architectural context for code generation.

        FIXED: For test generation, includes actual target file contents.
        """
        logger.info("Building A2 context for: %s...", goal[:50])

        # NEW: Detect if this is test generation
        is_test_generation = "test" in goal.lower() and target_file is not None

        # Get policies and placements
        policies = await self.policy_vectorizer.search_policies(query=goal, limit=5)
        placements = await self.anchor_generator.find_best_placement(
            code_description=goal, limit=3
        )
        if not placements:
            raise ValueError("No placement found for goal")

        best_placement = placements[0]
        layer = best_placement["layer"]
        layer_patterns = self._get_layer_patterns(layer)
        confidence = "high" if best_placement["score"] > 0.5 else "medium"

        # NEW: For test generation, read the actual target file
        target_file_content = None
        target_file_path = None

        if is_test_generation:
            (
                target_file_content,
                target_file_path,
            ) = await self._read_target_file_for_tests(goal, target_file)

        similar_examples = await self._find_similar_examples(
            goal=goal, layer=layer, module_path=best_placement["path"]
        )
        typical_deps = self._get_typical_dependencies(layer)
        reasoning = self._generate_placement_reasoning(
            goal=goal,
            layer=layer,
            best_placement=best_placement,
            alternative_placements=placements[1:] if len(placements) > 1 else [],
        )
        anti_patterns = self._get_anti_patterns(layer)

        return ArchitecturalContext(
            goal=goal,
            target_layer=layer,
            layer_purpose=best_placement["purpose"],
            layer_patterns=layer_patterns,
            relevant_policies=policies,
            placement_confidence=confidence,
            best_module_path=best_placement["path"],
            placement_score=best_placement["score"],
            similar_examples=similar_examples,
            typical_dependencies=typical_deps,
            placement_reasoning=reasoning,
            anti_patterns=anti_patterns,
            target_file_content=target_file_content,
            target_file_path=target_file_path,
        )

    async def _read_target_file_for_tests(
        self, goal: str, target_file: str
    ) -> tuple[str | None, str | None]:
        """
        NEW: Read the actual file that needs tests generated.

        Extracts the module path from the goal and reads the file.
        """
        try:
            # Extract module path from goal
            # Goal format: "Generate comprehensive tests for src/path/to/module.py"
            import re

            match = re.search(r"for\s+(src/[^\s]+\.py)", goal)
            if not match:
                logger.warning("Could not extract target module from goal: %s", goal)
                return None, None

            module_path = match.group(1)
            full_path = self.repo_root / module_path

            if not full_path.exists():
                logger.warning("Target file does not exist: %s", full_path)
                return None, None

            content = await asyncio.to_thread(
                lambda: full_path.read_text(encoding="utf-8")
            )

            logger.info(
                "Read target file for test generation: %s (%d chars)",
                module_path,
                len(content),
            )

            return content, module_path

        except Exception as e:
            logger.error("Failed to read target file: %s", e)
            return None, None

    async def _find_similar_examples(
        self, goal: str, layer: str, module_path: str
    ) -> list[CodeExample]:
        """Find similar code implementations for reference."""
        if not self.cognitive_service or not self.qdrant_service:
            return []
        try:
            embedding = await self.cognitive_service.get_embedding_for_code(goal)
            from qdrant_client import models as qm

            layer_filter = qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="metadata.layer", match=qm.MatchValue(value=layer)
                    )
                ]
            )
            search_results = await self.qdrant_service.search_similar(
                query_vector=embedding, limit=10, filter_=layer_filter
            )
            if not search_results:
                return []

            symbol_ids = []
            score_map = {}
            for result in search_results:
                payload = result.get("payload", {})
                symbol_id = payload.get("symbol_id")
                if symbol_id:
                    symbol_ids.append(symbol_id)
                    score_map[symbol_id] = result.get("score", 0.0)

            if not symbol_ids:
                return []

            async with get_session() as session:
                placeholders = ",".join([f":id{i}" for i in range(len(symbol_ids))])
                query = text(
                    f"SELECT id, qualname, file_path, docstring, line_number as start_line FROM core.symbols WHERE id IN ({placeholders})"
                )
                params = {f"id{i}": str(sid) for i, sid in enumerate(symbol_ids)}
                result = await session.execute(query, params)
                symbols = result.fetchall()

            examples = []
            for symbol in symbols[:5]:
                symbol_id, qualname, file_path, docstring, start_line = symbol
                try:
                    full_path = self.repo_root / file_path
                    if not full_path.exists():
                        continue
                    lines = await asyncio.to_thread(_read_file_lines_sync, full_path)
                    code_snippet = "".join(lines[start_line - 1 : start_line + 20])

                    examples.append(
                        CodeExample(
                            file_path=file_path,
                            symbol_name=qualname,
                            code_snippet=code_snippet,
                            purpose=docstring[:100] if docstring else "No description",
                            similarity_score=score_map.get(str(symbol_id), 0.0),
                        )
                    )
                except Exception:
                    continue
            return examples
        except Exception as e:
            logger.error("Error finding similar examples: %s", e)
            return []

    def _get_typical_dependencies(self, layer: str) -> list[str]:
        """Get typical import dependencies for a layer."""
        dependencies = {
            "shared": [
                "from __future__ import annotations",
                "from shared.logger import getLogger",
            ],
            "core": [
                "from __future__ import annotations",
                "from body.atomic.registry import register_action",
                "from shared.action_types import ActionResult",
            ],
            "will": [
                "from __future__ import annotations",
                "from shared.models import ExecutionTask",
            ],
            "services": [
                "from __future__ import annotations",
                "from shared.config import settings",
            ],
            "tests": [
                "from __future__ import annotations",
                "import pytest",
                "from sqlalchemy.orm import Session",
            ],
        }
        return dependencies.get(layer, [])

    def _generate_placement_reasoning(
        self,
        goal: str,
        layer: str,
        best_placement: dict[str, Any],
        alternative_placements: list[dict[str, Any]],
    ) -> str:
        reasoning_parts = [
            f"This code belongs in the '{layer}' layer because: {best_placement['purpose']}"
        ]
        score = best_placement["score"]
        if score > 0.7:
            reasoning_parts.append(
                f"The semantic match is strong (score: {score:.2f})."
            )
        return " ".join(reasoning_parts)

    def _get_anti_patterns(self, layer: str) -> list[str]:
        """Get common anti-patterns to avoid for a layer."""
        anti_patterns = {
            "core": [
                "DO NOT make autonomous decisions (delegate to will)",
                "DO NOT use legacy body.actions handlers",
                "DO NOT skip @register_action registration",
                "MUST return ActionResult with structured data",
            ],
            "will": [
                "DO NOT implement action execution (use body/atomic)",
                "DO NOT bypass ActionExecutor gateway",
            ],
            "tests": [
                "DO NOT import from src. prefix - imports should be direct",
                "DO NOT hallucinate models that don't exist",
                "MUST match actual model structure from target file",
            ],
        }
        return anti_patterns.get(layer, [])

    def _get_layer_patterns(self, layer: str) -> list[str]:
        patterns = {
            "shared": ["Pure utilities", "No side effects"],
            "core": [
                "Atomic Actions",
                "Strict Result Contract",
                "Governed Mutations",
            ],
            "will": ["Planning", "Orchestration", "Decision Making"],
            "tests": [
                "Comprehensive coverage",
                "Test actual implementations",
                "Use fixtures for database setup",
            ],
        }
        return patterns.get(layer, [])

    # ID: 51a52f37-a84f-42ef-aba7-e776032a979c
    def format_for_prompt(self, context: ArchitecturalContext) -> str:
        """
        Format architectural context for LLM prompt.

        FIXED: Includes target file content for test generation.
        """
        parts = [
            "# Architectural Context",
            "",
            f"**Goal:** {context.goal}",
            f"**Target Layer:** {context.target_layer}",
            f"**Layer Purpose:** {context.layer_purpose}",
            f"**Placement Confidence:** {context.placement_confidence}",
            "",
        ]

        # NEW: Include target file content if available (for test generation)
        if context.target_file_content and context.target_file_path:
            parts.extend(
                [
                    "## Target File to Test",
                    f"**File:** {context.target_file_path}",
                    "",
                    "```python",
                    context.target_file_content,
                    "```",
                    "",
                    "**CRITICAL:** Generate tests for the ACTUAL models shown above.",
                    "Do NOT hallucinate User, Project, or other models not present in the file.",
                    "",
                ]
            )

        if context.layer_patterns:
            parts.append("## Layer Patterns")
            for pattern in context.layer_patterns:
                parts.append(f"- {pattern}")
            parts.append("")

        if context.typical_dependencies:
            parts.append("## Typical Dependencies")
            for dep in context.typical_dependencies:
                parts.append(f"- {dep}")
            parts.append("")

        if context.anti_patterns:
            parts.append("## Anti-Patterns to Avoid")
            for anti in context.anti_patterns:
                parts.append(f"- {anti}")
            parts.append("")

        if context.similar_examples:
            parts.append("## Similar Examples for Reference")
            for example in context.similar_examples[:3]:
                parts.extend(
                    [
                        f"### {example.symbol_name} ({example.file_path})",
                        f"**Purpose:** {example.purpose}",
                        "```python",
                        example.code_snippet,
                        "```",
                        "",
                    ]
                )

        if context.relevant_policies:
            parts.append("## Relevant Constitutional Policies")
            for policy in context.relevant_policies[:3]:
                parts.append(f"- {policy.get('statement', 'N/A')}")
            parts.append("")

        return "\n".join(parts)
