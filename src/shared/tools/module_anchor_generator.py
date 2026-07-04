# src/shared/tools/module_anchor_generator.py
"""Module Anchor Generator — orchestrates anchor generation for layers and modules."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.tools.anchor_builder import (
    build_layer_anchor,
    build_module_anchor,
    get_layer_description_for_embedding,
    get_module_description_for_embedding,
)
from shared.tools.anchors.discovery import discover_modules_for_layers
from shared.tools.anchors.storage import ANCHOR_COLLECTION, ensure_anchor_collection
from shared.tools.layers import get_all_layers


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: dc5a79c0-e002-46ea-ac79-59003837311f
class ModuleAnchorGenerator:
    """Orchestrates generation of semantic anchors for architectural placement."""

    def __init__(
        self,
        repo_root: Path,
        cognitive_service: CognitiveService,
        qdrant_service: QdrantService,
    ):
        self.repo_root = Path(repo_root)
        self.src_dir = self.repo_root / "src"
        self.cognitive_service = cognitive_service
        self.qdrant = qdrant_service

    # ID: a66c5b38-2109-41f0-ba29-b20912566771
    async def find_best_placement(
        self, code_description: str, limit: int = 3
    ) -> list[dict[str, Any]]:
        from shared.tools import anchor_search

        return await anchor_search.find_best_placement(
            code_description=code_description,
            cognitive_service=self.cognitive_service,
            qdrant_service=self.qdrant,
            limit=limit,
        )

    # ID: ef29c8df-12fc-45cc-b26e-a7697c1f1abe
    async def generate_all_anchors(self) -> dict[str, Any]:
        """Generate all layer and module anchors."""
        logger.info("=" * 60)
        logger.info("PHASE 1: MODULE ANCHOR GENERATION")
        logger.info("=" * 60)

        if not self.src_dir.exists():
            return {"success": False, "error": "Source directory not found"}

        await ensure_anchor_collection(self.qdrant)
        results: dict[str, Any] = {"success": True, "anchors_created": 0, "errors": []}

        logger.info("\n📍 Generating layer-level anchors...")
        await self._generate_layer_anchors(results)

        logger.info("\n📍 Generating module-level anchors...")
        await self._generate_module_anchors(results)

        logger.info("\n" + "=" * 60)
        logger.info(
            "✅ ANCHOR GENERATION COMPLETE (Anchors: %s)", results["anchors_created"]
        )
        return results

    async def _generate_layer_anchors(self, results: dict[str, Any]) -> None:
        layers = get_all_layers()
        for layer_name, layer_purpose in layers.items():
            try:
                description = get_layer_description_for_embedding(layer_name)
                embedding = await self.cognitive_service.get_embedding_for_code(
                    description
                )
                if not embedding:
                    raise ValueError(f"Embedding failure for {layer_name}")
                point = build_layer_anchor(layer_name, embedding)
                await self.qdrant.upsert_points(
                    points=[point], collection_name=ANCHOR_COLLECTION
                )
                results["anchors_created"] += 1
                logger.info("  ✅ %s/", layer_name)
            except Exception as e:
                logger.error("  ❌ %s/: %s", layer_name, e)
                results["errors"].append({"module": layer_name, "error": str(e)})

    async def _generate_module_anchors(self, results: dict[str, Any]) -> None:
        layers = get_all_layers()
        modules = discover_modules_for_layers(self.src_dir, list(layers.keys()))
        logger.info("Found %s modules to anchor\n", len(modules))

        for module_path, module_info in modules.items():
            try:
                description = get_module_description_for_embedding(
                    module_path, module_info
                )
                embedding = await self.cognitive_service.get_embedding_for_code(
                    description
                )
                if not embedding:
                    raise ValueError(f"Embedding failure for {module_path}")
                point = build_module_anchor(module_path, module_info, embedding)
                await self.qdrant.upsert_points(
                    points=[point], collection_name=ANCHOR_COLLECTION
                )
                results["anchors_created"] += 1
                logger.info("  ✅ %s", module_path)
            except Exception as e:
                logger.error("  ❌ %s: %s", module_path, e)
                results["errors"].append({"module": str(module_path), "error": str(e)})
