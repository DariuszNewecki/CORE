# src/will/tools/architectural_context_builder.py
"""
Architectural Context Builder - Phase 1 Component

Builds rich architectural context for code generation prompts by combining:
- Policy search results (constitutional guidance)
- Module anchor data (semantic placement info)
- Layer-specific patterns

Constitutional Alignment:
- clarity_first: Explicit architectural guidance in prompts
- reason_with_purpose: Context-aware code generation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.logger import getLogger

from will.tools.module_anchor_generator import ModuleAnchorGenerator
from will.tools.policy_vectorizer import PolicyVectorizer

logger = getLogger(__name__)


@dataclass
# ID: 01cbdead-5514-408a-9a70-2ea2bc5f83ff
class ArchitecturalContext:
    """Rich context for code generation."""

    goal: str
    target_layer: str
    layer_purpose: str
    layer_patterns: list[str]
    relevant_policies: list[dict[str, Any]]
    placement_confidence: str
    best_module_path: str
    placement_score: float


# ID: 8c5f4d91-3e7a-4b9f-8a1f-9d2c3e4f5a6b
class ArchitecturalContextBuilder:
    """
    Builds rich architectural context for code generation.

    Combines policy search, module anchors, and layer patterns into
    a structured context package for LLM prompts.
    """

    def __init__(
        self,
        policy_vectorizer: PolicyVectorizer,
        anchor_generator: ModuleAnchorGenerator,
    ):
        """
        Initialize context builder.

        Args:
            policy_vectorizer: Service for searching policies
            anchor_generator: Service for finding module placement
        """
        self.policy_vectorizer = policy_vectorizer
        self.anchor_generator = anchor_generator

        logger.info("ArchitecturalContextBuilder initialized")

    # ID: 7b4c3d2e-1f0a-4b5c-8d9e-6f7a8b9c0d1e
    async def build_context(
        self,
        goal: str,
        target_file: str | None = None,
    ) -> ArchitecturalContext:
        """
        Build comprehensive architectural context for code generation.

        Args:
            goal: What the code should do
            target_file: Optional target file path (for validation)

        Returns:
            Structured architectural context
        """
        logger.info(f"Building context for: {goal[:50]}...")

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

        logger.info(
            f"Context built: layer={layer}, confidence={confidence}, "
            f"policies={len(policies)}"
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
        )

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

        Args:
            context: Architectural context

        Returns:
            Formatted string for LLM prompt
        """
        parts = []

        # Header
        parts.append("# Architectural Context")
        parts.append("")
        parts.append(f"**Goal**: {context.goal}")
        parts.append(f"**Target Layer**: {context.target_layer}")
        parts.append(f"**Placement Confidence**: {context.placement_confidence}")
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

        # Target location
        parts.append("## Target Location")
        parts.append("")
        parts.append(f"Place code in: `{context.best_module_path}`")
        parts.append("")

        return "\n".join(parts)
