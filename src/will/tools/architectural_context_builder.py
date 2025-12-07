# src/will/tools/architectural_context_builder.py
"""
Architectural Context Builder - A2 Enhanced

Builds rich architectural context for code generation prompts by combining:
- Policy search results (constitutional guidance)
- Module anchor data (semantic placement info)
- Layer-specific patterns
- Code examples from similar implementations (A2 NEW)
- Dependency patterns and imports (A2 NEW)
- Architectural reasoning explanations (A2 NEW)

Constitutional Alignment:
- clarity_first: Explicit architectural guidance in prompts
- reason_with_purpose: Context-aware code generation with examples
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import text

from will.tools.module_anchor_generator import ModuleAnchorGenerator
from will.tools.policy_vectorizer import PolicyVectorizer

if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


@dataclass
# ID: 5e8d4c3b-2a1f-9e8d-7c6b-5a4f3e2d1c0b
class CodeExample:
    """Represents a successful code implementation example."""

    file_path: str
    symbol_name: str
    code_snippet: str
    purpose: str
    similarity_score: float


@dataclass
# ID: 01cbdead-5514-408a-9a70-2ea2bc5f83ff
class ArchitecturalContext:
    """Rich context for code generation with A2 enhancements."""

    # Original fields
    goal: str
    target_layer: str
    layer_purpose: str
    layer_patterns: list[str]
    relevant_policies: list[dict[str, Any]]
    placement_confidence: str
    best_module_path: str
    placement_score: float

    # A2 NEW: Enhanced context fields
    similar_examples: list[CodeExample] = field(default_factory=list)
    typical_dependencies: list[str] = field(default_factory=list)
    placement_reasoning: str = ""
    common_patterns_in_module: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)


# ID: 8c5f4d91-3e7a-4b9f-8a1f-9d2c3e4f5a6b
class ArchitecturalContextBuilder:
    """
    Builds rich architectural context for code generation.

    Combines policy search, module anchors, and layer patterns into
    a structured context package for LLM prompts.

    A2 Enhanced: Now includes code examples, dependency analysis, and reasoning.
    """

    def __init__(
        self,
        policy_vectorizer: PolicyVectorizer,
        anchor_generator: ModuleAnchorGenerator,
        cognitive_service: CognitiveService | None = None,
        qdrant_service: QdrantService | None = None,
    ):
        """
        Initialize context builder.

        Args:
            policy_vectorizer: Service for searching policies
            anchor_generator: Service for finding module placement
            cognitive_service: Optional service for generating embeddings
            qdrant_service: Optional service for vector search
        """
        self.policy_vectorizer = policy_vectorizer
        self.anchor_generator = anchor_generator
        self.cognitive_service = cognitive_service
        self.qdrant_service = qdrant_service
        self.repo_root = settings.REPO_PATH

        logger.info("ArchitecturalContextBuilder (A2 Enhanced) initialized")

    # ID: 7b4c3d2e-1f0a-4b5c-8d9e-6f7a8b9c0d1e
    async def build_context(
        self,
        goal: str,
        target_file: str | None = None,
    ) -> ArchitecturalContext:
        """
        Build comprehensive architectural context for code generation.

        A2 Enhanced: Now includes similar code examples and dependency patterns.

        Args:
            goal: What the code should do
            target_file: Optional target file path (for validation)

        Returns:
            Structured architectural context with A2 enhancements
        """
        logger.info(f"Building A2 context for: {goal[:50]}...")

        # Step 1: Search for relevant constitutional policies
        logger.debug("Searching policies...")
        policies = await self.policy_vectorizer.search_policies(
            query=goal,
            limit=5,
        )

        # Step 2: Find best architectural placement
        logger.debug("Finding placement...")
        placements = await self.anchor_generator.find_best_placement(
            code_description=goal,
            limit=3,
        )

        if not placements:
            raise ValueError("No placement found for goal")

        best_placement = placements[0]

        # Step 3: Extract layer info
        layer = best_placement["layer"]
        layer_patterns = self._get_layer_patterns(layer)

        # Step 4: Determine confidence
        confidence = "high" if best_placement["score"] > 0.5 else "medium"

        # A2 NEW - Step 5: Find similar code examples
        logger.debug("Finding similar code examples...")
        similar_examples = await self._find_similar_examples(
            goal=goal,
            layer=layer,
            module_path=best_placement["path"],
        )

        # A2 NEW - Step 6: Extract typical dependencies
        logger.debug("Analyzing typical dependencies...")
        typical_deps = self._get_typical_dependencies(layer)

        # A2 NEW - Step 7: Generate placement reasoning
        logger.debug("Generating placement reasoning...")
        reasoning = self._generate_placement_reasoning(
            goal=goal,
            layer=layer,
            best_placement=best_placement,
            alternative_placements=placements[1:] if len(placements) > 1 else [],
        )

        # A2 NEW - Step 8: Identify anti-patterns
        anti_patterns = self._get_anti_patterns(layer)

        logger.info(
            f"A2 Context built: layer={layer}, confidence={confidence}, "
            f"policies={len(policies)}, examples={len(similar_examples)}"
        )

        return ArchitecturalContext(
            goal=goal,
            target_layer=layer,
            layer_purpose=best_placement["purpose"],
            layer_patterns=layer_patterns,
            relevant_policies=policies,
            placement_confidence=confidence,
            best_module_path=best_placement["path"],
            placement_score=best_placement["score"],
            # A2 NEW fields
            similar_examples=similar_examples,
            typical_dependencies=typical_deps,
            placement_reasoning=reasoning,
            anti_patterns=anti_patterns,
        )

    async def _find_similar_examples(
        self,
        goal: str,
        layer: str,
        module_path: str,
    ) -> list[CodeExample]:
        """
        A2 NEW: Find similar code implementations for reference.

        Queries the knowledge graph for semantically similar symbols in the same layer,
        retrieves their code from the filesystem, and returns top examples.

        Args:
            goal: What the code should do
            layer: Target layer
            module_path: Best module path

        Returns:
            List of similar code examples
        """
        if not self.cognitive_service or not self.qdrant_service:
            logger.debug("Cognitive/Qdrant services not available, skipping examples")
            return []

        try:
            # Step 1: Generate embedding for the goal
            logger.debug(f"Generating embedding for goal: {goal[:50]}...")
            embedding = await self.cognitive_service.get_embedding_for_code(goal)

            # Step 2: Search Qdrant for similar symbols with layer filter
            logger.debug("Searching for similar symbols in layer: %s", layer)
            # Note: Qdrant filter syntax - adjust if your payload structure differs
            from qdrant_client import models as qm

            layer_filter = qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="metadata.layer",
                        match=qm.MatchValue(value=layer),
                    )
                ]
            )

            search_results = await self.qdrant_service.search_similar(
                query_vector=embedding,
                limit=10,  # Get more candidates
                filter_=layer_filter,
            )

            if not search_results:
                logger.debug("No similar symbols found in vector search")
                return []

            # Step 3: Extract symbol IDs from search results
            symbol_ids = []
            score_map = {}
            for result in search_results:
                payload = result.get("payload", {})
                symbol_id = payload.get("symbol_id")
                if symbol_id:
                    symbol_ids.append(symbol_id)
                    score_map[symbol_id] = result.get("score", 0.0)

            if not symbol_ids:
                logger.debug("No valid symbol IDs in search results")
                return []

            # Step 4: Query DB for symbol details
            logger.debug(f"Fetching details for {len(symbol_ids)} symbols from DB")
            async with get_session() as session:
                # Build query to get symbol details
                placeholders = ",".join([f":id{i}" for i in range(len(symbol_ids))])
                query = text(
                    f"""
                    SELECT
                        id,
                        qualname,
                        file_path,
                        docstring,
                        start_line,
                        end_line
                    FROM core.symbols
                    WHERE id IN ({placeholders})
                    AND symbol_type IN ('function', 'class', 'method')
                    ORDER BY file_path
                """
                )

                params = {f"id{i}": str(sid) for i, sid in enumerate(symbol_ids)}
                result = await session.execute(query, params)
                symbols = result.fetchall()

            if not symbols:
                logger.debug("No symbol details found in database")
                return []

            # Step 5: Read code snippets from files
            examples = []
            for symbol in symbols[:5]:  # Limit to top 5
                symbol_id, qualname, file_path, docstring, start_line, end_line = symbol

                try:
                    # Read the actual code from the file
                    full_path = self.repo_root / file_path
                    if not full_path.exists():
                        logger.warning("File not found: %s", full_path)
                        continue

                    with open(full_path, encoding="utf-8") as f:
                        lines = f.readlines()

                    # Extract the code snippet
                    if start_line and end_line:
                        # Adjust for 1-based indexing
                        snippet_lines = lines[start_line - 1 : end_line]
                        code_snippet = "".join(snippet_lines)
                    else:
                        # Fallback: read first 20 lines
                        code_snippet = "".join(lines[:20])

                    # Truncate if too long
                    if len(code_snippet) > 500:
                        code_snippet = code_snippet[:500] + "\n    # ... (truncated)"

                    examples.append(
                        CodeExample(
                            file_path=file_path,
                            symbol_name=qualname,
                            code_snippet=code_snippet,
                            purpose=docstring[:100] if docstring else "No description",
                            similarity_score=score_map.get(str(symbol_id), 0.0),
                        )
                    )

                except Exception as e:
                    logger.warning("Failed to read code for {qualname}: %s", e)
                    continue

            logger.info(f"Found {len(examples)} similar code examples")
            return examples

        except Exception as e:
            logger.error(f"Error finding similar examples: {e}", exc_info=True)
            return []

    def _get_typical_dependencies(self, layer: str) -> list[str]:
        """
        A2 NEW: Get typical import dependencies for a layer.

        Args:
            layer: Layer name

        Returns:
            List of common imports for this layer
        """
        dependencies = {
            "shared": [
                "from __future__ import annotations",
                "from pathlib import Path",
                "from typing import Any",
            ],
            "domain": [
                "from __future__ import annotations",
                "from dataclasses import dataclass",
                "from shared.models import ValidationResult",
            ],
            "features": [
                "from __future__ import annotations",
                "from services.database.session_manager import get_session",
                "from shared.logger import getLogger",
            ],
            "will": [
                "from __future__ import annotations",
                "from will.orchestration.cognitive_service import CognitiveService",
                "from shared.logger import getLogger",
                "from shared.models import ExecutionTask",
            ],
            "core": [
                "from __future__ import annotations",
                "from body.actions.base import ActionHandler",
                "from shared.models import TaskParams",
            ],
            "services": [
                "from __future__ import annotations",
                "from shared.logger import getLogger",
                "from shared.config import settings",
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
        """
        A2 NEW: Generate human-readable reasoning for placement decision.

        Args:
            goal: What the code should do
            layer: Chosen layer
            best_placement: Best placement result
            alternative_placements: Other considered placements

        Returns:
            Reasoning explanation
        """
        reasoning_parts = []

        # Explain why this layer was chosen
        reasoning_parts.append(
            f"This code belongs in the '{layer}' layer because: {best_placement['purpose']}"
        )

        # Add confidence context
        score = best_placement["score"]
        if score > 0.7:
            reasoning_parts.append(
                f"The semantic match is strong (score: {score:.2f}), indicating high confidence."
            )
        elif score > 0.5:
            reasoning_parts.append(
                f"The semantic match is moderate (score: {score:.2f}), suggesting reasonable fit."
            )
        else:
            reasoning_parts.append(
                f"The semantic match is weak (score: {score:.2f}), review carefully."
            )

        # Mention alternatives if they exist
        if alternative_placements:
            alt_layers = [p.get("layer", "unknown") for p in alternative_placements]
            reasoning_parts.append(
                f"Alternative layers considered: {', '.join(alt_layers[:2])}"
            )

        return " ".join(reasoning_parts)

    def _get_anti_patterns(self, layer: str) -> list[str]:
        """
        A2 NEW: Get common anti-patterns to avoid for a layer.

        Args:
            layer: Layer name

        Returns:
            List of anti-patterns to avoid
        """
        anti_patterns = {
            "shared": [
                "DO NOT import from domain, features, or will layers",
                "DO NOT include business logic or decision-making",
                "DO NOT perform I/O operations (file, network, database)",
                "DO NOT maintain state or use global variables",
            ],
            "domain": [
                "DO NOT import services or infrastructure code",
                "DO NOT make API calls or database queries directly",
                "DO NOT handle HTTP requests or responses",
                "DO NOT use CognitiveService or LLM calls",
            ],
            "features": [
                "DO NOT implement low-level utilities (use shared instead)",
                "DO NOT bypass services for direct I/O",
                "DO NOT mix autonomous AI logic (use will layer)",
            ],
            "will": [
                "DO NOT implement action execution (use core/body instead)",
                "DO NOT bypass constitutional validation",
                "DO NOT hardcode prompts (use prompt templates)",
            ],
            "core": [
                "DO NOT make autonomous decisions (delegate to will)",
                "DO NOT skip ActionHandler base class",
                "DO NOT bypass ActionRegistry registration",
            ],
            "services": [
                "DO NOT embed business logic",
                "DO NOT skip error handling and retries",
                "DO NOT hardcode connection parameters",
            ],
        }

        return anti_patterns.get(layer, [])

    def _get_layer_patterns(self, layer: str) -> list[str]:
        """
        Get architectural patterns for a layer.

        Args:
            layer: Layer name (shared, domain, features, will, core)

        Returns:
            List of pattern descriptions
        """
        patterns = {
            "shared": [
                "Pure utility functions with no business logic",
                "No dependencies on domain, features, or will layers",
                "Reusable across entire codebase",
                "No side effects or I/O operations",
            ],
            "domain": [
                "Business logic and domain rules",
                "Return domain objects or ValidationResult",
                "No external dependencies (APIs, databases)",
                "Pure domain logic only",
            ],
            "features": [
                "High-level capabilities combining domain + infrastructure",
                "May use services and external dependencies",
                "Orchestrates multiple domain operations",
                "Public API for feature functionality",
            ],
            "will": [
                "Autonomous agents and AI decision-making",
                "Uses CognitiveService for LLM access",
                "Follows Agent base class patterns",
                "Constitutional compliance in all actions",
            ],
            "core": [
                "Action handlers for autonomous operations",
                "Extends ActionHandler base class",
                "Registers with ActionRegistry",
                "Constitutional validation before execution",
            ],
            "services": [
                "Infrastructure services (database, cache, APIs)",
                "External system integration",
                "Connection pooling and lifecycle management",
                "Error handling and retry logic",
            ],
        }

        return patterns.get(layer, [])

    # ID: 6e5d4c3b-2a1f-9e8d-7c6b-5a4f3e2d1c0b
    def format_for_prompt(self, context: ArchitecturalContext) -> str:
        """
        Format context into prompt-ready string.

        A2 Enhanced: Now includes code examples, dependencies, and reasoning.

        Args:
            context: Architectural context

        Returns:
            Formatted string for LLM prompt
        """
        parts = []

        # Header
        parts.append("# Architectural Context (A2 Enhanced)")
        parts.append("")
        parts.append(f"**Goal**: {context.goal}")
        parts.append(f"**Target Layer**: {context.target_layer}")
        parts.append(f"**Placement Confidence**: {context.placement_confidence}")
        parts.append("")

        # A2 NEW: Placement reasoning
        if context.placement_reasoning:
            parts.append("## Why This Placement?")
            parts.append("")
            parts.append(context.placement_reasoning)
            parts.append("")

        # Constitutional guidance
        if context.relevant_policies:
            parts.append("## Constitutional Requirements")
            parts.append("")
            parts.append("You MUST follow these rules:")
            parts.append("")
            for i, policy in enumerate(context.relevant_policies[:3], 1):
                parts.append(f"{i}. {policy['content'][:150]}")
            parts.append("")

        # Layer patterns
        parts.append("## Layer Patterns")
        parts.append("")
        parts.append(
            f"**{context.target_layer.capitalize()} Layer**: {context.layer_purpose}"
        )
        parts.append("")
        if context.layer_patterns:
            parts.append("**Architectural Patterns**:")
            for pattern in context.layer_patterns:
                parts.append(f"- {pattern}")
            parts.append("")

        # A2 NEW: Typical dependencies
        if context.typical_dependencies:
            parts.append("## Typical Imports")
            parts.append("")
            parts.append("Common imports for this layer:")
            parts.append("```python")
            for dep in context.typical_dependencies[:5]:
                parts.append(dep)
            parts.append("```")
            parts.append("")

        # A2 NEW: Similar examples
        if context.similar_examples:
            parts.append("## Similar Implementations")
            parts.append("")
            parts.append("Reference these successful examples from the codebase:")
            parts.append("")
            for i, example in enumerate(context.similar_examples[:3], 1):
                parts.append(f"**Example {i}**: {example.symbol_name}")
                parts.append(f"- File: `{example.file_path}`")
                parts.append(f"- Purpose: {example.purpose}")
                parts.append(f"- Similarity: {example.similarity_score:.2f}")
                parts.append("```python")
                parts.append(example.code_snippet[:300] + "...")
                parts.append("```")
                parts.append("")

        # A2 NEW: Anti-patterns
        if context.anti_patterns:
            parts.append("## Anti-Patterns (AVOID THESE)")
            parts.append("")
            for anti in context.anti_patterns:
                parts.append(f"- ❌ {anti}")
            parts.append("")

        # Target location
        parts.append("## Target Location")
        parts.append("")
        parts.append(f"Place code in: `{context.best_module_path}`")
        parts.append("")

        return "\n".join(parts)
