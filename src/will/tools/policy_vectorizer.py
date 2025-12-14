# src/will/tools/policy_vectorizer.py

"""
Policy Vectorization Service - Phase 1 Component

Transforms constitutional policy documents into semantic vectors, enabling
agents to query "what are the rules for X?" through vector search.

Constitutional Alignment:
- reason_with_purpose: Policies become semantically searchable
- clarity_first: Agents discover relevant rules by intent
- safe_by_default: Constitutional compliance through understanding

Phase 1 Goal: Enable context-aware code generation
Updated: Phase 1 - Vector Service Standardization
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.universal import get_deterministic_id
from shared.utils.yaml_processor import strict_yaml_processor
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
POLICY_COLLECTION = "core_policies"


# ID: 106d06ad-6291-4deb-8af1-8edafba3f45d
class PolicyVectorizer:
    """
    Vectorizes constitutional policies for semantic search.

    Enables agents to query "rules for creating validators" and receive
    relevant constitutional guidance without hardcoded rule matching.

    Phase 1 Updates:
    - Uses QdrantService methods instead of direct client access
    - Implements hash-based deduplication
    - Follows vector_service_standards.yaml
    """

    def __init__(
        self,
        repo_root: Path,
        cognitive_service: CognitiveService,
        qdrant_service: QdrantService,
    ):
        """
        Initialize policy vectorizer.

        Args:
            repo_root: Path to CORE repository root
            cognitive_service: Service for generating embeddings
            qdrant_service: Vector database service
        """
        self.repo_root = Path(repo_root)
        self.policies_dir = self.repo_root / ".intent" / "charter" / "policies"
        self.cognitive_service = cognitive_service
        self.qdrant = qdrant_service
        logger.info("PolicyVectorizer initialized for %s", self.policies_dir)

    # ID: af476d73-c1d9-4c1d-b6a1-4ac73806b82b
    async def initialize_collection(self) -> None:
        """
        Create Qdrant collection for policy vectors if it doesn't exist.

        Uses 768-dimensional vectors (nomic-embed-text default).
        Uses CORE's ensure_collection pattern for idempotent creation.

        PHASE 1: Uses service client (allowed during transition).
        """
        try:
            from qdrant_client import models as qm

            collections_response = await self.qdrant.client.get_collections()
            existing = [c.name for c in collections_response.collections]
            if POLICY_COLLECTION in existing:
                logger.info("Collection %s already exists", POLICY_COLLECTION)
                return
            logger.info("Creating collection: %s", POLICY_COLLECTION)
            await self.qdrant.client.recreate_collection(
                collection_name=POLICY_COLLECTION,
                vectors_config=qm.VectorParams(size=768, distance=qm.Distance.COSINE),
                on_disk_payload=True,
            )
            logger.info("✅ Collection %s created", POLICY_COLLECTION)
        except Exception as e:
            logger.error("Failed to initialize collection: %s", e, exc_info=True)
            raise

    # ID: c10418a1-7dbe-4b26-90cd-e87e1711bc1b
    async def vectorize_all_policies(self) -> dict[str, Any]:
        """
        Vectorize all policy documents in .intent/charter/policies/

        PHASE 1: Now uses hash-based deduplication to skip unchanged policies.

        Returns:
            Summary with counts and any errors
        """
        logger.info("=" * 60)
        logger.info("PHASE 1: POLICY VECTORIZATION")
        logger.info("=" * 60)
        if not self.policies_dir.exists():
            logger.error("❌ Policies directory not found: %s", self.policies_dir)
            return {
                "success": False,
                "error": "Policies directory not found",
                "policies_vectorized": 0,
            }
        await self.initialize_collection()
        stored_hashes = await self.qdrant.get_stored_hashes(POLICY_COLLECTION)
        logger.debug("Retrieved %s existing policy hashes", len(stored_hashes))
        policy_files = list(self.policies_dir.glob("*.yaml"))
        logger.info("Found %s policy files", len(policy_files))
        logger.info("")
        results = {
            "success": True,
            "policies_vectorized": 0,
            "chunks_created": 0,
            "errors": [],
        }
        for policy_file in policy_files:
            try:
                policy_result = await self._vectorize_policy_file(
                    policy_file, stored_hashes
                )
                results["policies_vectorized"] += 1
                results["chunks_created"] += policy_result["chunks"]
                count = policy_result["chunks"]
                if count > 0:
                    logger.info("  ✅ {policy_file.name}: %s chunks vectorized", count)
                else:
                    logger.debug("  Skipped %s (unchanged)", policy_file.name)
            except Exception as e:
                logger.error("  ❌ %s: %s", policy_file.name, e, exc_info=True)
                results["errors"].append({"file": policy_file.name, "error": str(e)})
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ VECTORIZATION COMPLETE")
        logger.info("   Policies: %s", results["policies_vectorized"])
        logger.info("   Chunks: %s", results["chunks_created"])
        if results["errors"]:
            logger.warning("   Errors: %s", len(results["errors"]))
        logger.info("=" * 60)
        return results

    async def _vectorize_policy_file(
        self, policy_file: Path, stored_hashes: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        Vectorize a single policy file.

        PHASE 1: Updated to use service methods.
        PHASE 2 PREP: Accepts stored_hashes for future deduplication.

        Args:
            policy_file: Path to policy YAML file
            stored_hashes: Optional pre-fetched hashes for deduplication

        Returns:
            Summary with chunk count
        """
        policy_data = strict_yaml_processor.load(policy_file)
        policy_id = policy_data.get("id", policy_file.stem)
        policy_title = policy_data.get("title", policy_id)
        chunks = self._extract_policy_chunks(policy_data, policy_id, policy_file.name)
        valid_chunks = []
        if stored_hashes:
            for chunk in chunks:
                chunk_id = f"{chunk['policy_id']}_{chunk['type']}_{chunk.get('rule_id', 'unknown')}"
                point_id = str(get_deterministic_id(chunk_id))
                normalized_content = chunk["content"].strip()
                content_hash = hashlib.sha256(
                    normalized_content.encode("utf-8")
                ).hexdigest()
                if (
                    point_id in stored_hashes
                    and stored_hashes[point_id] == content_hash
                ):
                    continue
                valid_chunks.append(chunk)
        else:
            valid_chunks = chunks
        if not valid_chunks:
            return {"policy_id": policy_id, "chunks": 0}
        for chunk in valid_chunks:
            await self._store_policy_chunk(chunk)
        return {"policy_id": policy_id, "chunks": len(valid_chunks)}

    def _extract_policy_chunks(
        self, policy_data: dict[str, Any], policy_id: str, filename: str
    ) -> list[dict[str, Any]]:
        """
        Extract semantic chunks from policy document.

        Args:
            policy_data: Parsed policy YAML
            policy_id: Policy identifier
            filename: Policy filename

        Returns:
            List of chunks with content and metadata
        """
        chunks = []
        if "title" in policy_data and "purpose" in policy_data:
            chunks.append(
                {
                    "type": "policy_purpose",
                    "policy_id": policy_id,
                    "filename": filename,
                    "content": f"{policy_data['title']}\n\nPurpose: {policy_data['purpose']}",
                    "metadata": {"version": policy_data.get("version", "unknown")},
                }
            )
        if "agent_rules" in policy_data:
            for rule in policy_data["agent_rules"]:
                chunks.append(
                    {
                        "type": "agent_rule",
                        "policy_id": policy_id,
                        "filename": filename,
                        "rule_id": rule.get("id", "unknown"),
                        "content": f"Rule: {rule.get('statement', '')}",
                        "metadata": {"enforcement": rule.get("enforcement", "unknown")},
                    }
                )
        if "autonomy_lanes" in policy_data:
            lanes = policy_data["autonomy_lanes"]
            if "micro_proposals" in lanes:
                micro = lanes["micro_proposals"]
                allowed = micro.get("allowed_actions", [])[:10]
                chunks.append(
                    {
                        "type": "autonomy_lane",
                        "policy_id": policy_id,
                        "filename": filename,
                        "lane_type": "micro_proposals",
                        "content": f"{micro.get('description', '')}\n\nAllowed actions: {', '.join(allowed)}",
                        "metadata": {
                            "safe_paths": micro.get("safe_paths", [])[:5],
                            "forbidden_paths": micro.get("forbidden_paths", [])[:5],
                        },
                    }
                )
        if "style_rules" in policy_data:
            for rule in policy_data["style_rules"]:
                if isinstance(rule, dict):
                    chunks.append(
                        {
                            "type": "code_standard",
                            "policy_id": policy_id,
                            "filename": filename,
                            "rule_id": rule.get("id", "unknown"),
                            "content": f"Standard: {rule.get('statement', '')}",
                            "metadata": {
                                "enforcement": rule.get("enforcement", "warn")
                            },
                        }
                    )
        if "safety_rules" in policy_data:
            for rule in policy_data["safety_rules"]:
                if isinstance(rule, dict):
                    chunks.append(
                        {
                            "type": "safety_rule",
                            "policy_id": policy_id,
                            "filename": filename,
                            "rule_id": rule.get("id", "unknown"),
                            "content": f"Safety Rule: {rule.get('statement', '')}",
                            "metadata": {
                                "enforcement": rule.get("enforcement", "error"),
                                "protected_paths": rule.get("protected_paths", [])[:5],
                            },
                        }
                    )
        return chunks

    async def _store_policy_chunk(self, chunk: dict[str, Any]) -> None:
        """
        Generate embedding and store chunk in Qdrant.

        PHASE 1: Now includes content_sha256 hash in payload.

        Args:
            chunk: Policy chunk with content and metadata
        """
        embedding = await self.cognitive_service.get_embedding_for_code(
            chunk["content"]
        )
        if not embedding:
            logger.warning(
                "Failed to generate embedding for chunk: %s",
                chunk.get("rule_id", "unknown"),
            )
            return
        chunk_id = (
            f"{chunk['policy_id']}_{chunk['type']}_{chunk.get('rule_id', 'unknown')}"
        )
        normalized_content = chunk["content"].strip()
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
        from qdrant_client.models import PointStruct

        point_id = get_deterministic_id(chunk_id)
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "policy_id": chunk["policy_id"],
                "filename": chunk["filename"],
                "type": chunk["type"],
                "content": chunk["content"],
                "metadata": chunk.get("metadata", {}),
                "content_sha256": content_hash,
            },
        )
        await self.qdrant.upsert_points(
            collection_name=POLICY_COLLECTION, points=[point]
        )

    # ID: 5f79e8a2-8cde-4245-ad6f-b4bd355b238c
    async def search_policies(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search for relevant policy chunks.

        PHASE 1: Uses service client (direct access allowed for search).

        Args:
            query: Search query (e.g., "rules for creating action handlers")
            limit: Maximum number of results

        Returns:
            List of relevant policy chunks with scores
        """
        logger.info("Searching policies for: %s", query)
        query_embedding = await self.cognitive_service.get_embedding_for_code(query)
        if not query_embedding:
            logger.warning("Failed to generate query embedding")
            return []
        try:
            results = await self.qdrant.client.search(
                collection_name=POLICY_COLLECTION,
                query_vector=query_embedding,
                limit=limit,
            )
            formatted_results = []
            for hit in results:
                formatted_results.append(
                    {
                        "score": hit.score,
                        "policy_id": hit.payload["policy_id"],
                        "type": hit.payload["type"],
                        "content": hit.payload["content"],
                        "metadata": hit.payload.get("metadata", {}),
                    }
                )
            logger.info("Found %s relevant policy chunks", len(formatted_results))
            return formatted_results
        except Exception as e:
            logger.error("Policy search failed: %s", e, exc_info=True)
            return []


# ID: 64c63d13-45c0-4ef5-9001-42703a6158a6
async def vectorize_policies_command(repo_root: Path) -> dict[str, Any]:
    """
    CLI command wrapper for policy vectorization.

    Usage:
        from will.tools.policy_vectorizer import vectorize_policies_command
        result = await vectorize_policies_command(Path("/opt/dev/CORE"))

    Args:
        repo_root: Path to CORE repository

    Returns:
        Vectorization results summary
    """
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

    qdrant_service = QdrantService()
    cognitive_service = CognitiveService(
        repo_path=repo_root, qdrant_service=qdrant_service
    )
    await cognitive_service.initialize()
    vectorizer = PolicyVectorizer(repo_root, cognitive_service, qdrant_service)
    results = await vectorizer.vectorize_all_policies()
    return results


if __name__ == "__main__":
    import sys

    repo_root = Path.cwd()
    if len(sys.argv) > 1:
        repo_root = Path(sys.argv[1])
    result = asyncio.run(vectorize_policies_command(repo_root))
    logger.info("\nVectorization complete!")
    logger.info("  Policies: %s", result["policies_vectorized"])
    logger.info("  Chunks: %s", result["chunks_created"])
    if result.get("errors"):
        logger.info("  Errors: %s", len(result["errors"]))
        for error in result["errors"]:
            logger.info("    - %s: %s", error["file"], error["error"])
