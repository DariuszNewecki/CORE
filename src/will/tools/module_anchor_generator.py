# src/will/tools/module_anchor_generator.py

"""
Module Anchor Generator - Orchestrates anchor generation for layers and modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

from .anchor_builder import (
    build_layer_anchor,
    build_module_anchor,
    get_layer_description_for_embedding,
    get_module_description_for_embedding,
)
from .anchors.discovery import discover_modules_for_layers
from .anchors.storage import ANCHOR_COLLECTION, ensure_anchor_collection
from .layers import get_all_layers


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

    # ID: ef29c8df-12fc-45cc-b26e-a7697c1f1abe
    async def generate_all_anchors(self) -> dict[str, Any]:
        """Generate all layer and module anchors."""
        logger.info("=" * 60)
        logger.info("PHASE 1: MODULE ANCHOR GENERATION")
        logger.info("=" * 60)

        if not self.src_dir.exists():
            return {"success": False, "error": "Source directory not found"}

        await ensure_anchor_collection(self.qdrant)
        results = {"success": True, "anchors_created": 0, "errors": []}

        # Generate layer anchors
        logger.info("\n📍 Generating layer-level anchors...")
        await self._generate_layer_anchors(results)

        # Generate module anchors
        logger.info("\n📍 Generating module-level anchors...")
        await self._generate_module_anchors(results)

        logger.info("\n" + "=" * 60)
        logger.info(
            "✅ ANCHOR GENERATION COMPLETE (Anchors: %s)", results["anchors_created"]
        )
        return results

    async def _generate_layer_anchors(self, results: dict[str, Any]) -> None:
        """Generate anchors for all architectural layers."""
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
        """Generate anchors for all discovered modules."""
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
