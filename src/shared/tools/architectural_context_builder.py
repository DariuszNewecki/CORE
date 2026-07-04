# src/shared/tools/architectural_context_builder.py
"""Builds rich architectural context for code generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.tools.context import standards
from shared.tools.context.models import ArchitecturalContext
from shared.tools.context.retriever import ContextRetriever


if TYPE_CHECKING:
    from shared.tools.module_anchor_generator import ModuleAnchorGenerator
    from shared.tools.policy_vectorizer import PolicyVectorizer

logger = getLogger(__name__)


# ID: 5abea787-be57-49d1-8792-767a34cc4b67
class ArchitecturalContextBuilder:
    def __init__(
        self,
        policy_vectorizer: PolicyVectorizer,
        anchor_generator: ModuleAnchorGenerator,
        path_resolver: PathResolver,
        session_factory: Any,
        cognitive_service: Any = None,
        qdrant_service: Any = None,
    ):
        self.policies = policy_vectorizer
        self.anchors = anchor_generator
        self._paths = path_resolver
        self._session_factory = session_factory
        self.retriever = ContextRetriever(
            self._paths.repo_root, cognitive_service, qdrant_service
        )

    # ID: 256ec235-24e3-426a-aba1-9f37d06843bd
    async def build_context(
        self, goal: str, target_file: str | None = None
    ) -> ArchitecturalContext:
        logger.info("🧠 Building Context: %s", goal[:50])

        policy_hits = await self.policies.search_policies(query=goal, limit=5)
        placements = await self.anchors.find_best_placement(
            code_description=goal, limit=3
        )
        if not placements:
            raise ValueError("No architectural anchor found.")
        best = placements[0]

        is_test = "test" in goal.lower()
        file_content, file_path = (None, None)
        if is_test:
            file_content, file_path = await self.retriever.read_target_file(
                goal, target_file
            )

        async with self._session_factory() as session:
            examples = await self.retriever.find_examples(goal, best["layer"], session)

        return ArchitecturalContext(
            goal=goal,
            target_layer=best["layer"],
            layer_purpose=best["purpose"],
            layer_patterns=standards.get_layer_patterns(best["layer"]),
            relevant_policies=policy_hits,
            placement_confidence="high" if best["score"] > 0.5 else "medium",
            best_module_path=best["path"],
            placement_score=best["score"],
            similar_examples=examples,
            typical_dependencies=standards.get_typical_deps(best["layer"]),
            anti_patterns=standards.get_anti_patterns(best["layer"]),
            target_file_content=file_content,
            target_file_path=file_path,
        )

    # ID: 2cfa04d7-7b21-4f4b-8cf0-77cbc4f7415f
    def format_for_prompt(self, context: ArchitecturalContext) -> str:
        from shared.tools.context.formatter import format_context_to_markdown

        return format_context_to_markdown(context)
