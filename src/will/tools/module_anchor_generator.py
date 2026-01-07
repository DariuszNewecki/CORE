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

CONSTITUTIONAL FIX:
- Implements 'Defensive Loop Guard' to satisfy async.no_manual_loop_run.
- Complies with RUF006 using a module-level task registry to prevent GC.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from typing import Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.universal import get_deterministic_id
from will.orchestration.cognitive_service import CognitiveService
from will.tools.module_descriptor import ModuleDescriptor


logger = getLogger(__name__)
ANCHOR_COLLECTION = "core_module_anchors"

# RUF006 FIX: Persistent set to hold references to running tasks
_RUNNING_TASKS: set[asyncio.Task] = set()

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


# ID: a82c9417-3f62-4441-8985-522b89e1c90d
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
        logger.info("ModuleAnchorGenerator initialized for %s", self.src_dir)

    # ID: 22e1df4d-2609-4e8e-a486-a604581e161b
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

    # ID: ebf164c4-36b7-4f7e-9a39-186124a598fa
    async def generate_all_anchors(self) -> dict[str, Any]:
        """Generate anchors for all modules in the codebase."""
        logger.info("=" * 60)
        logger.info("PHASE 1: MODULE ANCHOR GENERATION")
        logger.info("=" * 60)
        if not self.src_dir.exists():
            return {"success": False, "error": "Source directory not found"}
        await self.initialize_collection()
        results = {"success": True, "anchors_created": 0, "errors": []}
        logger.info("\n📍 Generating layer-level anchors...")
        for layer_name, layer_purpose in LAYERS.items():
            try:
                await self._generate_layer_anchor(layer_name, layer_purpose)
                results["anchors_created"] += 1
                logger.info("  ✅ %s/", layer_name)
            except Exception as e:
                logger.error("  ❌ {layer_name}/: %s", e)
                results["errors"].append({"module": layer_name, "error": str(e)})
        logger.info("\n📍 Generating module-level anchors...")
        modules = self._discover_modules()
        logger.info("Found %s modules to anchor\n", len(modules))
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
        logger.info("   Anchors: %s", results["anchors_created"])
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
                if item.is_dir() and (not item.name.startswith("_")):
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
        """
        from qdrant_client.models import PointStruct

        description = f"Layer: {layer_name}\n\nPurpose: {layer_purpose}\n\nThis is a top-level architectural layer in CORE's Mind-Body-Will structure."
        embedding = await self.cognitive_service.get_embedding_for_code(description)
        if not embedding:
            raise ValueError(f"Failed to generate embedding for layer {layer_name}")
        point_id = get_deterministic_id(f"layer_{layer_name}")
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "type": "layer",
                "name": layer_name,
                "path": f"src/{layer_name}/",
                "purpose": layer_purpose,
                "description": description,
            },
        )
        await self.qdrant.upsert_points(
            points=[point], collection_name=ANCHOR_COLLECTION
        )

    async def _generate_module_anchor(
        self, module_path: Path, module_info: dict[str, Any]
    ) -> None:
        """
        Generate anchor for specific module with rich descriptions.
        """
        from qdrant_client.models import PointStruct

        layer = module_info["layer"]
        files = module_info["python_files"]
        module_description = ModuleDescriptor.generate(
            str(module_path), module_path.name, layer, files
        )
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
        point_id = get_deterministic_id(f"module_{module_path}")
        point = PointStruct(
            id=point_id,
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
        await self.qdrant.upsert_points(
            points=[point], collection_name=ANCHOR_COLLECTION
        )

    # ID: 6198547e-ae81-4ac1-9c04-f459ce5a93e2
    async def find_best_placement(
        self, code_description: str, limit: int = 3
    ) -> list[dict[str, Any]]:
        """Find best placement for code based on semantic similarity."""
        logger.info("Finding placement for: %s...", code_description[:50])
        embedding = await self.cognitive_service.get_embedding_for_code(
            code_description
        )
        if not embedding:
            return []
        module_results = await self.qdrant.client.search(
            collection_name=ANCHOR_COLLECTION,
            query_vector=embedding,
            limit=limit * 2,
            query_filter={"must": [{"key": "type", "match": {"value": "module"}}]},
        )
        if not module_results:
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
            "Found %s module placements (best: %s, score: %s)",
            len(placements),
            placements[0]["path"],
            placements[0]["score"],
        )
        return placements


# ID: d302e11c-67da-4c3a-b0fc-6295cb450f06
async def generate_anchors_command(repo_root: Path) -> dict[str, Any]:
    """CLI command wrapper for anchor generation."""
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

    qdrant_service = QdrantService()
    cognitive_service = CognitiveService(
        repo_path=repo_root, qdrant_service=qdrant_service
    )
    await cognitive_service.initialize()
    generator = ModuleAnchorGenerator(repo_root, cognitive_service, qdrant_service)
    return await generator.generate_all_anchors()


# ID: a6f2c56a-c121-4ac5-ba3e-3cb49cb28dcb
def run_as_script():
    """
    Constitutional entry point for standalone execution.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate module anchors for the CORE codebase."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the CORE repository root.",
    )

    args = parser.parse_args()

    async def _main() -> None:
        """Internal main logic."""
        result = await generate_anchors_command(args.repo_root)
        logger.info("\nAnchor generation complete!")
        logger.info("  Anchors: %s", result["anchors_created"])
        if result.get("errors"):
            logger.info("  Errors: %s", len(result["errors"]))

    # THE DEFENSIVE GUARD:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # RUF006 COMPLIANCE: Use a strong reference in a module-level set.
        # This prevents the linter from flagging the task as 'dangling'.
        task = asyncio.create_task(_main())
        _RUNNING_TASKS.add(task)
        task.add_done_callback(_RUNNING_TASKS.discard)
    else:
        asyncio.run(_main())


if __name__ == "__main__":
    run_as_script()
