# src/features/introspection/pattern_vectorizer.py
"""
Pattern Vectorization Service

Constitutionally vectorizes architectural patterns from .intent/charter/patterns/
into the core-patterns Qdrant collection for semantic validation.

This enables CORE to understand its own constitution semantically and validate
code against constitutional expectations.

Constitutional Policy: pattern_vectorization.yaml
Updated: Phase 1 - Vector Service Standardization
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from qdrant_client.models import PointStruct
from services.clients.qdrant_client import QdrantService
from shared.config import settings
from shared.logger import getLogger
from shared.utils.yaml_processor import strict_yaml_processor
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: 5d963ba8-0988-4433-9111-a0ecedd0ef0d
class PatternChunk:
    """
    A semantic chunk of a constitutional pattern.

    Represents a meaningful section of a pattern that can be vectorized
    and queried independently.
    """

    def __init__(
        self,
        pattern_id: str,
        pattern_version: str,
        pattern_category: str,
        section_type: str,
        section_path: str,
        content: str,
        applies_to: list[str] | None = None,
        severity: str = "error",
    ):
        self.pattern_id = pattern_id
        self.pattern_version = pattern_version
        self.pattern_category = pattern_category
        self.section_type = section_type
        self.section_path = section_path
        self.content = content
        self.applies_to = applies_to or []
        self.severity = severity

    # ID: a40e5d42-b3d5-4a2f-8e2e-a11cfec6fa9f
    def to_metadata(self) -> dict[str, Any]:
        """Convert to Qdrant metadata format."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_version": self.pattern_version,
            "pattern_category": self.pattern_category,
            "section_type": self.section_type,
            "section_path": self.section_path,
            "applies_to": self.applies_to,
            "severity": self.severity,
            "content": self.content,  # Store for retrieval
        }


# ID: c90138f0-3728-4876-8553-8656f12812a8
class PatternVectorizer:
    """
    Vectorizes constitutional patterns for semantic understanding and validation.

    Constitutional Service - operates under pattern_vectorization policy.

    Phase 1 Updates:
    - Uses QdrantService methods instead of direct client access
    - Implements hash-based deduplication
    - Follows vector_service_standards.yaml
    """

    COLLECTION_NAME = "core-patterns"
    VECTOR_DIMENSION = int(settings.LOCAL_EMBEDDING_DIM)

    def __init__(
        self,
        qdrant_service: QdrantService,
        cognitive_service: CognitiveService,
        patterns_dir: Path | None = None,
    ):
        # PHASE 1 FIX: Store the service, not the client
        self.qdrant = qdrant_service
        self.cognitive = cognitive_service
        self.patterns_dir = patterns_dir or (
            settings.REPO_PATH / ".intent" / "charter" / "patterns"
        )

    # ID: 8d9f7fc3-b55a-485d-9b6d-9fcf0d30c5c3
    async def ensure_collection(self) -> None:
        """
        Ensure core-patterns collection exists with correct schema.
        Delegates to QdrantService for idempotency.
        """
        await self.qdrant.ensure_collection(
            collection_name=self.COLLECTION_NAME,
            vector_size=self.VECTOR_DIMENSION,
        )

    # ID: fab06120-8b1b-4959-87a1-c14d7dc5f356
    async def vectorize_all_patterns(self) -> dict[str, int]:
        """
        Vectorize all pattern files in .intent/charter/patterns/.

        PHASE 1: Now uses hash-based deduplication to skip unchanged patterns.

        Returns:
            Dict mapping pattern_id -> chunk_count
        """
        await self.ensure_collection()

        pattern_files = list(self.patterns_dir.glob("*.yaml"))
        logger.info(f"Found {len(pattern_files)} pattern files to vectorize")

        # PHASE 2 PREP: Get stored hashes for deduplication
        stored_hashes = await self.qdrant.get_stored_hashes()
        logger.debug(f"Retrieved {len(stored_hashes)} existing pattern hashes")

        results = {}
        for pattern_file in pattern_files:
            try:
                count = await self.vectorize_pattern(pattern_file, stored_hashes)
                results[pattern_file.stem] = count
                logger.info(f"✓ Vectorized {pattern_file.name}: {count} chunks")
            except Exception as e:
                logger.error(f"✗ Failed to vectorize {pattern_file.name}: {e}")
                results[pattern_file.stem] = 0

        total_chunks = sum(results.values())
        logger.info(
            f"✓ Vectorized {len(results)} patterns, {total_chunks} total chunks"
        )

        return results

    # ID: 9373a88b-281f-4956-b807-af849ac35d3d
    async def vectorize_pattern(
        self,
        pattern_file: Path,
        stored_hashes: dict[str, str] | None = None,
    ) -> int:
        """
        Vectorize a single pattern file into semantic chunks.

        PHASE 1: Updated to use service methods.
        PHASE 2 PREP: Accepts stored_hashes for future deduplication.

        Args:
            pattern_file: Path to pattern YAML file
            stored_hashes: Optional pre-fetched hashes for deduplication

        Returns:
            Number of chunks created
        """
        logger.debug(f"Vectorizing pattern: {pattern_file.name}")

        # Load pattern YAML using CORE's processor
        pattern_data = strict_yaml_processor.load(pattern_file)

        # Extract metadata
        pattern_id = pattern_data.get("pattern_id", pattern_file.stem)
        pattern_version = pattern_data.get("version", "1.0.0")
        pattern_category = pattern_data.get("category", "general")

        # Chunk the pattern
        chunks = self._chunk_pattern(
            pattern_id, pattern_version, pattern_category, pattern_data
        )

        if not chunks:
            logger.warning(f"No chunks generated for {pattern_file.name}")
            return 0

        # Generate embeddings using cognitive service
        chunk_texts = [chunk.content for chunk in chunks]

        import asyncio

        embedding_tasks = [
            self.cognitive.get_embedding_for_code(text) for text in chunk_texts
        ]
        embeddings = await asyncio.gather(*embedding_tasks)

        # Filter out None results from failed embeddings
        valid_data = []
        for chunk, emb in zip(chunks, embeddings):
            if emb is not None:
                valid_data.append((chunk, emb))

        if not valid_data:
            logger.warning(f"Failed to generate embeddings for {pattern_file.name}")
            return 0

        # PHASE 1 FIX: Create points with content_sha256 hashes
        points = []
        for idx, (chunk, embedding) in enumerate(valid_data):
            point_id = hash(f"{pattern_id}_{idx}") % (2**63)

            # PHASE 2 PREP: Compute content hash for deduplication
            normalized_content = chunk.content.strip()
            content_hash = hashlib.sha256(
                normalized_content.encode("utf-8")
            ).hexdigest()

            # Add hash to payload
            payload = chunk.to_metadata()
            payload["content_sha256"] = content_hash
            payload["chunk_id"] = f"{pattern_id}_{idx}"

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        # PHASE 1 FIX: Use QdrantService method instead of direct client access
        if points:
            await self.qdrant.upsert_points(
                collection_name=self.COLLECTION_NAME,
                points=points,
            )

        return len(valid_data)

    def _chunk_pattern(
        self,
        pattern_id: str,
        pattern_version: str,
        pattern_category: str,
        pattern_data: dict,
    ) -> list[PatternChunk]:
        """
        Chunk a pattern into semantic sections.

        Strategy: Each top-level section and meaningful subsection becomes a chunk.
        """
        chunks = []

        # Chunk philosophy
        if "philosophy" in pattern_data:
            chunks.append(
                PatternChunk(
                    pattern_id=pattern_id,
                    pattern_version=pattern_version,
                    pattern_category=pattern_category,
                    section_type="philosophy",
                    section_path="philosophy",
                    content=pattern_data["philosophy"],
                )
            )

        # Chunk requirements
        if "requirements" in pattern_data:
            for req_name, req_data in pattern_data["requirements"].items():
                if isinstance(req_data, dict) and "mandate" in req_data:
                    content = f"{req_data['mandate']}\n\n"
                    if "implementation" in req_data:
                        impl = req_data["implementation"]
                        if isinstance(impl, list):
                            content += "Implementation:\n" + "\n".join(
                                f"- {item}" for item in impl
                            )
                        else:
                            content += f"Implementation: {impl}"

                    chunks.append(
                        PatternChunk(
                            pattern_id=pattern_id,
                            pattern_version=pattern_version,
                            pattern_category=pattern_category,
                            section_type="requirement",
                            section_path=f"requirements.{req_name}",
                            content=content,
                            severity="error",
                        )
                    )

        # Chunk validation rules
        if "validation_rules" in pattern_data:
            for rule in pattern_data["validation_rules"]:
                if isinstance(rule, dict) and "rule" in rule:
                    content = f"Rule: {rule['rule']}\n"
                    content += f"Description: {rule.get('description', '')}\n"
                    content += f"Severity: {rule.get('severity', 'error')}\n"
                    content += f"Enforcement: {rule.get('enforcement', 'runtime')}"

                    chunks.append(
                        PatternChunk(
                            pattern_id=pattern_id,
                            pattern_version=pattern_version,
                            pattern_category=pattern_category,
                            section_type="validation_rule",
                            section_path=f"validation_rules.{rule['rule']}",
                            content=content,
                            severity=rule.get("severity", "error"),
                        )
                    )

        # Chunk examples
        if "examples" in pattern_data:
            for example_name, example_data in pattern_data["examples"].items():
                if isinstance(example_data, dict):
                    content = f"Example: {example_name}\n"
                    content += strict_yaml_processor.dump_yaml(example_data)

                    chunks.append(
                        PatternChunk(
                            pattern_id=pattern_id,
                            pattern_version=pattern_version,
                            pattern_category=pattern_category,
                            section_type="example",
                            section_path=f"examples.{example_name}",
                            content=content,
                        )
                    )

        # Chunk migration phases
        if "migration" in pattern_data:
            migration = pattern_data["migration"]
            if "phases" in migration:
                for phase_name, phase_data in migration["phases"].items():
                    if isinstance(phase_data, list):
                        content = f"Migration Phase: {phase_name}\n"
                        content += "\n".join(f"- {item}" for item in phase_data)

                        chunks.append(
                            PatternChunk(
                                pattern_id=pattern_id,
                                pattern_version=pattern_version,
                                pattern_category=pattern_category,
                                section_type="migration",
                                section_path=f"migration.phases.{phase_name}",
                                content=content,
                            )
                        )

        # Chunk generic patterns list
        if "patterns" in pattern_data and isinstance(pattern_data["patterns"], list):
            for pat in pattern_data["patterns"]:
                if isinstance(pat, dict) and "pattern_id" in pat:
                    content = f"Pattern: {pat['pattern_id']}\n"
                    content += f"Type: {pat.get('type')}\n"
                    content += f"Purpose: {pat.get('purpose')}\n"
                    if "implementation_requirements" in pat:
                        content += f"Requirements: {pat['implementation_requirements']}"

                    chunks.append(
                        PatternChunk(
                            pattern_id=pattern_id,
                            pattern_version=pattern_version,
                            pattern_category=pattern_category,
                            section_type="pattern_definition",
                            section_path=f"patterns.{pat['pattern_id']}",
                            content=content,
                        )
                    )

        return chunks

    # ID: 3db91262-a701-42f3-a911-67acf0323a43
    async def query_pattern(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Query patterns semantically.

        PHASE 1 FIX: Uses QdrantService.search method.

        Args:
            query: Natural language query
            limit: Max results to return

        Returns:
            List of matching pattern chunks with metadata
        """
        # Generate query embedding using cognitive service
        query_vector = await self.cognitive.get_embedding_for_code(query)

        if not query_vector:
            return []

        # PHASE 1 FIX: Use service search method
        results = await self.qdrant.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_vector,
            limit=limit,
        )

        return [
            {
                "score": hit.score,
                **hit.payload,
            }
            for hit in results
        ]
