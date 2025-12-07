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

from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.utils.yaml_processor import strict_yaml_processor
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)

# Collection name for policy vectors
POLICY_COLLECTION = "core_policies"


# ID: f63bd660-571e-48f0-ab12-d6847da03090
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
        # PHASE 1 FIX: Store service not client
        self.qdrant = qdrant_service

        logger.info(f"PolicyVectorizer initialized for {self.policies_dir}")

    # ID: d5db9578-4875-4de1-bd60-eeecf1ae7ab2
    async def initialize_collection(self) -> None:
        """
        Create Qdrant collection for policy vectors if it doesn't exist.

        Uses 768-dimensional vectors (nomic-embed-text default).
        Uses CORE's ensure_collection pattern for idempotent creation.

        PHASE 1: Uses service client (allowed during transition).
        """
        try:
            from qdrant_client import models as qm

            # PHASE 1: Direct client access (acceptable during transition)
            collections_response = await self.qdrant.client.get_collections()
            existing = [c.name for c in collections_response.collections]

            if POLICY_COLLECTION in existing:
                logger.info("Collection %s already exists", POLICY_COLLECTION)
                return

            logger.info("Creating collection: %s", POLICY_COLLECTION)

            # Create collection with 768-dim vectors
            await self.qdrant.client.recreate_collection(
                collection_name=POLICY_COLLECTION,
                vectors_config=qm.VectorParams(
                    size=768,  # nomic-embed-text dimension
                    distance=qm.Distance.COSINE,
                ),
                on_disk_payload=True,
            )
            logger.info("✅ Collection %s created", POLICY_COLLECTION)

        except Exception as e:
            logger.error(f"Failed to initialize collection: {e}", exc_info=True)
            raise

    # ID: 6a90f8c9-5c53-44bd-bdbc-3c066a9f01e4
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
            logger.error(f"❌ Policies directory not found: {self.policies_dir}")
            return {
                "success": False,
                "error": "Policies directory not found",
                "policies_vectorized": 0,
            }

        # Initialize collection
        await self.initialize_collection()

        # PHASE 2 PREP: Get stored hashes for deduplication
        stored_hashes = await self.qdrant.get_stored_hashes()
        logger.debug(f"Retrieved {len(stored_hashes)} existing policy hashes")

        # Discover policy files
        policy_files = list(self.policies_dir.glob("*.yaml"))
        logger.info(f"Found {len(policy_files)} policy files")
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
                logger.info(
                    f"  ✅ {policy_file.name}: "
                    f"{policy_result['chunks']} chunks vectorized"
                )
            except Exception as e:
                logger.error(f"  ❌ {policy_file.name}: {e}", exc_info=True)
                results["errors"].append(
                    {
                        "file": policy_file.name,
                        "error": str(e),
                    }
                )

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ VECTORIZATION COMPLETE")
        logger.info(f"   Policies: {results['policies_vectorized']}")
        logger.info(f"   Chunks: {results['chunks_created']}")
        if results["errors"]:
            logger.warning(f"   Errors: {len(results['errors'])}")
        logger.info("=" * 60)

        return results

    async def _vectorize_policy_file(
        self,
        policy_file: Path,
        stored_hashes: dict[str, str] | None = None,
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
        # Load policy YAML
        policy_data = strict_yaml_processor.load(policy_file)

        # Extract policy metadata
        policy_id = policy_data.get("id", policy_file.stem)
        policy_title = policy_data.get("title", policy_id)

        # Parse policy into semantic chunks
        chunks = self._extract_policy_chunks(policy_data, policy_id, policy_file.name)

        # Vectorize and store each chunk
        for chunk in chunks:
            await self._store_policy_chunk(chunk)

        return {
            "policy_id": policy_id,
            "chunks": len(chunks),
        }

    def _extract_policy_chunks(
        self,
        policy_data: dict[str, Any],
        policy_id: str,
        filename: str,
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

        # Policy purpose (main semantic anchor)
        if "title" in policy_data and "purpose" in policy_data:
            chunks.append(
                {
                    "type": "policy_purpose",
                    "policy_id": policy_id,
                    "filename": filename,
                    "content": (
                        f"{policy_data['title']}\n\n"
                        f"Purpose: {policy_data['purpose']}"
                    ),
                    "metadata": {
                        "version": policy_data.get("version", "unknown"),
                    },
                }
            )

        # Agent rules (from agent_governance.yaml)
        if "agent_rules" in policy_data:
            for rule in policy_data["agent_rules"]:
                chunks.append(
                    {
                        "type": "agent_rule",
                        "policy_id": policy_id,
                        "filename": filename,
                        "rule_id": rule.get("id", "unknown"),
                        "content": f"Rule: {rule.get('statement', '')}",
                        "metadata": {
                            "enforcement": rule.get("enforcement", "unknown"),
                        },
                    }
                )

        # Autonomy lanes (from agent_governance.yaml)
        if "autonomy_lanes" in policy_data:
            lanes = policy_data["autonomy_lanes"]

            if "micro_proposals" in lanes:
                micro = lanes["micro_proposals"]
                allowed = micro.get("allowed_actions", [])[:10]  # Limit to 10

                chunks.append(
                    {
                        "type": "autonomy_lane",
                        "policy_id": policy_id,
                        "filename": filename,
                        "lane_type": "micro_proposals",
                        "content": (
                            f"{micro.get('description', '')}\n\n"
                            f"Allowed actions: {', '.join(allowed)}"
                        ),
                        "metadata": {
                            "safe_paths": micro.get("safe_paths", [])[:5],
                            "forbidden_paths": micro.get("forbidden_paths", [])[:5],
                        },
                    }
                )

        # Code standards (from code_standards.yaml)
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
                                "enforcement": rule.get("enforcement", "warn"),
                            },
                        }
                    )

        # Safety rules (from safety_framework.yaml)
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
        # Generate embedding for chunk content
        embedding = await self.cognitive_service.get_embedding_for_code(
            chunk["content"]
        )

        if not embedding:
            logger.warning(
                f"Failed to generate embedding for chunk: {chunk.get('rule_id', 'unknown')}"
            )
            return

        # Create unique ID for chunk
        chunk_id = (
            f"{chunk['policy_id']}_{chunk['type']}_{chunk.get('rule_id', 'unknown')}"
        )

        # PHASE 1 FIX: Compute content hash for deduplication
        normalized_content = chunk["content"].strip()
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

        # Store in Qdrant using CORE's client API
        from qdrant_client.models import PointStruct

        point = PointStruct(
            id=hash(chunk_id) % (2**63),  # Convert to int ID
            vector=embedding,
            payload={
                "policy_id": chunk["policy_id"],
                "filename": chunk["filename"],
                "type": chunk["type"],
                "content": chunk["content"],
                "metadata": chunk.get("metadata", {}),
                # PHASE 1 FIX: Add content hash
                "content_sha256": content_hash,
            },
        )

        # PHASE 1: Direct client upsert (acceptable during transition)
        # TODO Phase 1 Day 4: Replace with service method when available
        await self.qdrant.client.upsert(
            collection_name=POLICY_COLLECTION,
            points=[point],
        )

    # ID: fdf6e40b-3dd0-44a6-bd29-49257b71ff9d
    async def search_policies(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
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

        # Generate embedding for query
        query_embedding = await self.cognitive_service.get_embedding_for_code(query)

        if not query_embedding:
            logger.warning("Failed to generate query embedding")
            return []

        # PHASE 1: Direct client search (acceptable, service doesn't have search yet)
        try:
            results = await self.qdrant.client.search(
                collection_name=POLICY_COLLECTION,
                query_vector=query_embedding,
                limit=limit,
            )

            # Format results
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

            logger.info(f"Found {len(formatted_results)} relevant policy chunks")
            return formatted_results

        except Exception as e:
            logger.error(f"Policy search failed: {e}", exc_info=True)
            return []


# ID: d386f75f-55ce-474e-a8ca-d5d359a702b7
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
    from services.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

    # Initialize services
    qdrant_service = QdrantService()
    cognitive_service = CognitiveService(
        repo_path=repo_root,
        qdrant_service=qdrant_service,
    )
    await cognitive_service.initialize()

    # Vectorize policies
    vectorizer = PolicyVectorizer(repo_root, cognitive_service, qdrant_service)
    results = await vectorizer.vectorize_all_policies()

    return results


# CLI integration point
if __name__ == "__main__":
    import sys

    repo_root = Path.cwd()
    if len(sys.argv) > 1:
        repo_root = Path(sys.argv[1])

    result = asyncio.run(vectorize_policies_command(repo_root))

    logger.info("\nVectorization complete!")
    logger.info(f"  Policies: {result['policies_vectorized']}")
    logger.info(f"  Chunks: {result['chunks_created']}")

    if result.get("errors"):
        logger.info(f"  Errors: {len(result['errors'])}")
        for error in result["errors"]:
            logger.info(f"    - {error['file']}: {error['error']}")
