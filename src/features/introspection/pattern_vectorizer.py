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

from shared.config import settings
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.universal import get_deterministic_id
from shared.utils.yaml_processor import strict_yaml_processor
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: da5ef4a5-7913-46d9-aab5-5aa985255a5c
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

    # ID: 386b7dc4-0dd3-46a5-b241-de878fbc97a2
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
            "content": self.content,
        }


# ID: b444f603-4d22-4556-88e5-124651b86a02
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
        self.qdrant = qdrant_service
        self.cognitive = cognitive_service
        self.patterns_dir = (
            patterns_dir or settings.REPO_PATH / ".intent" / "charter" / "patterns"
        )

    # ID: 822d1ba3-c18a-4870-bcbc-b10eb831ef00
    async def ensure_collection(self) -> None:
        """
        Ensure core-patterns collection exists with correct schema.
        Delegates to QdrantService for idempotency.
        """
        await self.qdrant.ensure_collection(
            collection_name=self.COLLECTION_NAME, vector_size=self.VECTOR_DIMENSION
        )

    # ID: 8c051a57-4d3f-44df-bea6-547a611bb8c1
    async def vectorize_all_patterns(self) -> dict[str, int]:
        """
        Vectorize all pattern files in .intent/charter/patterns/.

        PHASE 1: Now uses hash-based deduplication to skip unchanged patterns.

        Returns:
            Dict mapping pattern_id -> chunk_count
        """
        await self.ensure_collection()
        pattern_files = list(self.patterns_dir.glob("*.yaml"))
        logger.info("Found %s pattern files to vectorize", len(pattern_files))
        stored_hashes = await self.qdrant.get_stored_hashes(self.COLLECTION_NAME)
        logger.debug("Retrieved %s existing pattern hashes", len(stored_hashes))
        results = {}
        for pattern_file in pattern_files:
            try:
                count = await self.vectorize_pattern(pattern_file, stored_hashes)
                results[pattern_file.stem] = count
                if count > 0:
                    logger.info("✓ Vectorized %s: %s chunks", pattern_file.name, count)
                else:
                    logger.debug("Skipped %s (unchanged)", pattern_file.name)
            except Exception as e:
                logger.error("✗ Failed to vectorize %s: %s", pattern_file.name, e)
                results[pattern_file.stem] = 0
        total_chunks = sum(results.values())
        logger.info(
            "✓ Vectorized %s patterns, %s total chunks", len(results), total_chunks
        )
        return results

    # ID: da6def3c-6397-4dea-84cc-7a803c8bcbc6
    async def vectorize_pattern(
        self, pattern_file: Path, stored_hashes: dict[str, str] | None = None
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
        logger.debug("Vectorizing pattern: %s", pattern_file.name)
        pattern_data = strict_yaml_processor.load(pattern_file)
        pattern_id = pattern_data.get("pattern_id", pattern_file.stem)
        pattern_version = pattern_data.get("version", "1.0.0")
        pattern_category = pattern_data.get("category", "general")
        chunks = self._chunk_pattern(
            pattern_id, pattern_version, pattern_category, pattern_data
        )
        if not chunks:
            logger.warning("No chunks generated for %s", pattern_file.name)
            return 0
        valid_chunks = []
        if stored_hashes:
            for idx, chunk in enumerate(chunks):
                chunk_id_str = f"{pattern_id}_{idx}"
                point_id = str(get_deterministic_id(chunk_id_str))
                normalized_content = chunk.content.strip()
                content_hash = hashlib.sha256(
                    normalized_content.encode("utf-8")
                ).hexdigest()
                if (
                    point_id in stored_hashes
                    and stored_hashes[point_id] == content_hash
                ):
                    continue
                valid_chunks.append((idx, chunk))
        else:
            valid_chunks = list(enumerate(chunks))
        if not valid_chunks:
            return 0
        logger.info(
            "Processing %s new/changed chunks for %s",
            len(valid_chunks),
            pattern_file.name,
        )
        chunk_texts = [chunk.content for _, chunk in valid_chunks]
        import asyncio

        embedding_tasks = [
            self.cognitive.get_embedding_for_code(text) for text in chunk_texts
        ]
        embeddings = await asyncio.gather(*embedding_tasks)
        points = []
        for (idx, chunk), embedding in zip(valid_chunks, embeddings):
            if not embedding:
                continue
            chunk_id_str = f"{pattern_id}_{idx}"
            point_id = get_deterministic_id(chunk_id_str)
            normalized_content = chunk.content.strip()
            content_hash = hashlib.sha256(
                normalized_content.encode("utf-8")
            ).hexdigest()
            payload = chunk.to_metadata()
            payload["content_sha256"] = content_hash
            payload["chunk_id"] = chunk_id_str
            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))
        if points:
            await self.qdrant.upsert_points(
                collection_name=self.COLLECTION_NAME, points=points
            )
        return len(points)

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

    # ID: dcd6d244-c869-4b50-8956-11e9ee8331b0
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
        query_vector = await self.cognitive.get_embedding_for_code(query)
        if not query_vector:
            return []
        results = await self.qdrant.search(
            collection_name=self.COLLECTION_NAME, query_vector=query_vector, limit=limit
        )
        return [{"score": hit.score, **hit.payload} for hit in results]
