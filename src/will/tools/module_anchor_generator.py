# src/will/tools/module_anchor_generator.py
"""
Module Anchor Generator - Phase 1 Component

Generates semantic "anchor" vectors for each architectural layer/module,
enabling mathematical placement decisions based on semantic distance.

Constitutional Alignment:
- evolvable_structure: Architectural awareness through embeddings
- clarity_first: Explicit module purposes as vectors
- reason_with_purpose: Placement decisions based on semantic similarity

Phase 1 Goal: Fix 45% → 90%+ semantic placement
Phase 1 Update: Uses QdrantService.upsert_points() service method
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.tools.module_descriptor import ModuleDescriptor


logger = getLogger(__name__)

# Collection name for module anchors
ANCHOR_COLLECTION = "core_module_anchors"

# Architectural layers in CORE
LAYERS = {
    "mind": "Constitutional governance, policies, and validation rules",
    "body": "Pure execution - CLI commands, actions, no decision-making",
    "will": "Autonomous agents and AI decision-making",
    "services": "Infrastructure orchestration with external systems (DB, APIs, caches)",
    "shared": "Pure utilities with no external dependencies or state",
    "domain": "Business logic and domain rules without external dependencies",
    "features": "High-level capabilities combining domain + services",
    "core": "Action handlers for autonomous operations",
}


# ID: 53e91db6-3e5a-4b9f-9f3a-c7635ad41a00
class ModuleAnchorGenerator:
    """Generates semantic anchors for architectural modules."""

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
        logger.info(f"ModuleAnchorGenerator initialized for {self.src_dir}")

    # ID: 419623b4-afd7-4648-969d-c345f653f268
    async def initialize_collection(self) -> None:
        """Create Qdrant collection for module anchors if it doesn't exist."""
        from qdrant_client import models as qm

        collections_response = await self.qdrant.client.get_collections()
        existing = [c.name for c in collections_response.collections]

        if ANCHOR_COLLECTION in existing:
            logger.info("Collection %s already exists", ANCHOR_COLLECTION)
            return

        logger.info("Creating collection: %s", ANCHOR_COLLECTION)
        await self.qdrant.client.recreate_collection(
            collection_name=ANCHOR_COLLECTION,
            vectors_config=qm.VectorParams(size=768, distance=qm.Distance.COSINE),
            on_disk_payload=True,
        )
        logger.info("✅ Collection %s created", ANCHOR_COLLECTION)

    # ID: 32cc2cc0-8cd3-4e22-85fa-3b680cb38200
    async def generate_all_anchors(self) -> dict[str, Any]:
        """Generate anchors for all modules in the codebase."""
        logger.info("=" * 60)
        logger.info("PHASE 1: MODULE ANCHOR GENERATION")
        logger.info("=" * 60)

        if not self.src_dir.exists():
            return {"success": False, "error": "Source directory not found"}

        await self.initialize_collection()

        results = {"success": True, "anchors_created": 0, "errors": []}

        # Generate layer-level anchors
        logger.info("\n📍 Generating layer-level anchors...")
        for layer_name, layer_purpose in LAYERS.items():
            try:
                await self._generate_layer_anchor(layer_name, layer_purpose)
                results["anchors_created"] += 1
                logger.info("  ✅ %s/", layer_name)
            except Exception as e:
                logger.error("  ❌ {layer_name}/: %s", e)
                results["errors"].append({"module": layer_name, "error": str(e)})

        # Generate module-level anchors
        logger.info("\n📍 Generating module-level anchors...")
        modules = self._discover_modules()
        logger.info(f"Found {len(modules)} modules to anchor\n")

        for module_path, module_info in modules.items():
            try:
                await self._generate_module_anchor(module_path, module_info)
                results["anchors_created"] += 1
                logger.info("  ✅ %s", module_path)
            except Exception as e:
                logger.error("  ❌ {module_path}: %s", e)
                results["errors"].append({"module": str(module_path), "error": str(e)})

        logger.info("\n" + "=" * 60)
        logger.info("✅ ANCHOR GENERATION COMPLETE")
        logger.info(f"   Anchors: {results['anchors_created']}")
        logger.info("=" * 60)

        return results

    def _discover_modules(self) -> dict[Path, dict[str, Any]]:
        """Discover all modules (directories with Python files)."""
        modules = {}

        for layer_name in LAYERS.keys():
            layer_dir = self.src_dir / layer_name
            if not layer_dir.exists():
                continue

            for item in layer_dir.rglob("*"):
                if item.is_dir() and not item.name.startswith("_"):
                    py_files = list(item.glob("*.py"))
                    if py_files:
                        relative_path = item.relative_to(self.src_dir)
                        modules[relative_path] = {
                            "layer": layer_name,
                            "docstring": self._extract_module_docstring(item),
                            "file_count": len(py_files),
                            "python_files": [f.name for f in py_files[:5]],
                        }

        return modules

    def _extract_module_docstring(self, module_dir: Path) -> str | None:
        """Extract module-level docstring from __init__.py."""
        init_file = module_dir / "__init__.py"
        if not init_file.exists():
            return None

        try:
            content = init_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            if tree.body and isinstance(tree.body[0], ast.Expr):
                if isinstance(tree.body[0].value, ast.Constant):
                    return tree.body[0].value.value
        except Exception:
            pass

        return None

    async def _generate_layer_anchor(self, layer_name: str, layer_purpose: str) -> None:
        """
        Generate anchor for architectural layer.

        PHASE 1: Uses upsert_points() service method instead of direct client access.
        """
        from qdrant_client.models import PointStruct

        description = f"Layer: {layer_name}\n\nPurpose: {layer_purpose}\n\nThis is a top-level architectural layer in CORE's Mind-Body-Will structure."

        embedding = await self.cognitive_service.get_embedding_for_code(description)
        if not embedding:
            raise ValueError(f"Failed to generate embedding for layer {layer_name}")

        point = PointStruct(
            id=hash(f"layer_{layer_name}") % (2**63),
            vector=embedding,
            payload={
                "type": "layer",
                "name": layer_name,
                "path": f"src/{layer_name}/",
                "purpose": layer_purpose,
                "description": description,
            },
        )

        # PHASE 1: Use service method
        await self.qdrant.upsert_points(
            points=[point],
            collection_name=ANCHOR_COLLECTION,
        )

    async def _generate_module_anchor(
        self, module_path: Path, module_info: dict[str, Any]
    ) -> None:
        """
        Generate anchor for specific module with rich descriptions.

        PHASE 1: Uses upsert_points() service method instead of direct client access.
        """
        from qdrant_client.models import PointStruct

        layer = module_info["layer"]
        files = module_info["python_files"]

        # Use ModuleDescriptor for rich descriptions
        module_description = ModuleDescriptor.generate(
            str(module_path), module_path.name, layer, files
        )

        # Build full description
        parts = [
            f"Module: {module_path}",
            f"Architectural Layer: {layer}",
            f"Layer Purpose: {LAYERS[layer]}",
            "",
            f"Module Purpose: {module_description}",
            f"\nExample Files: {', '.join(files[:3])}",
        ]
        description = "\n".join(parts)

        embedding = await self.cognitive_service.get_embedding_for_code(description)
        if not embedding:
            raise ValueError(f"Failed to generate embedding for module {module_path}")

        point = PointStruct(
            id=hash(f"module_{module_path}") % (2**63),
            vector=embedding,
            payload={
                "type": "module",
                "name": module_path.name,
                "path": f"src/{module_path}/",
                "layer": layer,
                "purpose": module_description,
                "description": description,
                "file_count": module_info["file_count"],
                "example_files": files,
            },
        )

        # PHASE 1: Use service method
        await self.qdrant.upsert_points(
            points=[point],
            collection_name=ANCHOR_COLLECTION,
        )

    # ID: a19384a4-0138-4bb3-b0c5-b024150d1b54
    async def find_best_placement(
        self, code_description: str, limit: int = 3
    ) -> list[dict[str, Any]]:
        """Find best placement for code based on semantic similarity."""
        logger.info(f"Finding placement for: {code_description[:50]}...")

        embedding = await self.cognitive_service.get_embedding_for_code(
            code_description
        )
        if not embedding:
            return []

        # PHASE 1: Direct client search is acceptable (no service method yet)
        # Search ALL modules directly
        module_results = await self.qdrant.client.search(
            collection_name=ANCHOR_COLLECTION,
            query_vector=embedding,
            limit=limit * 2,
            query_filter={"must": [{"key": "type", "match": {"value": "module"}}]},
        )

        if not module_results:
            # Fallback to layers
            layer_results = await self.qdrant.client.search(
                collection_name=ANCHOR_COLLECTION,
                query_vector=embedding,
                limit=limit,
                query_filter={"must": [{"key": "type", "match": {"value": "layer"}}]},
            )
            return [
                {
                    "score": hit.score,
                    "type": "layer",
                    "path": hit.payload["path"],
                    "name": hit.payload["name"],
                    "purpose": hit.payload["purpose"],
                    "layer": hit.payload["name"],
                    "confidence": "high" if hit.score > 0.5 else "medium",
                }
                for hit in layer_results
            ]

        placements = [
            {
                "score": hit.score,
                "type": "module",
                "path": hit.payload["path"],
                "name": hit.payload["name"],
                "purpose": hit.payload.get("purpose", ""),
                "layer": hit.payload["layer"],
                "confidence": "high" if hit.score > 0.5 else "medium",
            }
            for hit in module_results[:limit]
        ]

        logger.info(
            f"Found {len(placements)} module placements "
            f"(best: {placements[0]['path']}, score: {placements[0]['score']:.3f})"
        )
        return placements


# CLI integration
# ID: 229b44b7-ed04-45f3-8045-b992aa018c18
async def generate_anchors_command(repo_root: Path) -> dict[str, Any]:
    """CLI command wrapper for anchor generation."""
    from services.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

    qdrant_service = QdrantService()
    cognitive_service = CognitiveService(
        repo_path=repo_root, qdrant_service=qdrant_service
    )
    await cognitive_service.initialize()

    generator = ModuleAnchorGenerator(repo_root, cognitive_service, qdrant_service)
    return await generator.generate_all_anchors()


if __name__ == "__main__":
    import asyncio
    import sys

    repo_root = Path.cwd() if len(sys.argv) == 1 else Path(sys.argv[1])
    result = asyncio.run(generate_anchors_command(repo_root))

    logger.info("\nAnchor generation complete!")
    logger.info(f"  Anchors: {result['anchors_created']}")
    if result.get("errors"):
        logger.info(f"  Errors: {len(result['errors'])}")
