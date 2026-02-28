# src/will/agents/strategic_auditor/context_gatherer.py

"""
SystemContextGatherer — collects the full system state for strategic reasoning.

Six dimensions of self-awareness:
    1. constitutional_health  — AST + .intent/   (what rules am I violating?)
    2. semantic_landscape     — Qdrant vectors   (what concepts am I built from?)
    3. knowledge_gaps         — DB + vectors     (where am I blind to myself?)
    4. structural_health      — DB symbols       (what do I contain?)
    5. change_context         — git              (what am I becoming?)
    6. intent_drift           — vectors + DB     (where does meaning diverge from code?)

Never writes anything.
"""

from __future__ import annotations

import math
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from shared.context import CoreContext
    from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Gatherer
# ---------------------------------------------------------------------------


# ID: sa-context-gatherer
# ID: 92a68530-9125-4393-8407-9c06c1333486
class SystemContextGatherer:
    """
    Collects the full six-dimension system state for StrategicAuditor reasoning.

    CognitiveService is held for future embedding generation (e.g. query-time
    semantic search). Current Qdrant access goes through context.qdrant_service.
    """

    def __init__(self, context: CoreContext, cognitive_service: CognitiveService):
        self._ctx = context
        self._cognitive = cognitive_service

    # ID: sa-gather-all
    # ID: 0a1b56cc-6a69-4425-bf2e-3b23a10b8f69
    async def gather(self, session: AsyncSession) -> dict[str, Any]:
        """Gather all six dimensions of system state."""
        logger.info("📡 Gathering system context across 6 dimensions...")

        audit_findings = await self._gather_constitutional_health(session)
        structural_health = await self._gather_structural_health(session)
        knowledge_gaps = await self._gather_knowledge_gaps(session)
        semantic_landscape, intent_drift = await self._gather_vector_dimensions(session)
        change_context = self._gather_change_context()
        constitution_summary = self._gather_constitution_summary()

        return {
            "audit_findings": audit_findings,  # Dim 1
            "semantic_landscape": semantic_landscape,  # Dim 2
            "knowledge_gaps": knowledge_gaps,  # Dim 3
            "structural_health": structural_health,  # Dim 4
            "change_context": change_context,  # Dim 5
            "intent_drift": intent_drift,  # Dim 6
            # Legacy aliases for prompt compatibility
            "knowledge_graph_summary": structural_health,
            "constitution_summary": constitution_summary,
            "git_delta": change_context,
            "gathered_at": datetime.now(UTC).isoformat(),
        }

    # -------------------------------------------------------------------------
    # Dimension 1: Constitutional Health
    # -------------------------------------------------------------------------

    # ID: sa-gather-constitutional-health
    async def _gather_constitutional_health(
        self, session: AsyncSession
    ) -> list[dict[str, Any]]:
        """
        What rules am I violating?

        Runs the real constitutional audit (same engine as core-admin check audit).
        All 81 rules execute — including knowledge_gate and workflow_gate.
        """
        from mind.governance.audit_context import AuditorContext
        from mind.governance.auditor import ConstitutionalAuditor

        repo_path = self._ctx.git_service.repo_path
        logger.info("🔍 [Dim 1] Running full constitutional audit...")

        audit_context = AuditorContext(repo_path=repo_path, session_provider=None)
        audit_context.db_session = session

        auditor = ConstitutionalAuditor(audit_context)
        results = await auditor.run_full_audit_async()
        audit_context.db_session = None

        findings = results.get("findings", [])
        all_findings: list[dict[str, Any]] = []

        for f in findings:
            if hasattr(f, "as_dict"):
                d = f.as_dict()
            else:
                d = {
                    "rule_id": getattr(f, "check_id", "unknown"),
                    "severity": str(getattr(f, "severity", "info")).lower(),
                    "message": getattr(f, "message", ""),
                    "file": str(getattr(f, "file_path", "") or ""),
                    "context": getattr(f, "context", {}),
                }
            all_findings.append(d)

        verdict = results.get("verdict")
        logger.info(
            "📋 [Dim 1] %d findings, verdict=%s",
            len(all_findings),
            verdict.value if verdict else "unknown",
        )
        return all_findings

    # -------------------------------------------------------------------------
    # Dimension 2 + 6: Semantic Landscape & Intent Drift (single Qdrant scroll)
    # -------------------------------------------------------------------------

    # ID: sa-gather-vector-dimensions
    async def _gather_vector_dimensions(
        self,
        session: AsyncSession,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Gather dimensions 2 and 6.

        Dim 2 (semantic landscape): scroll core_capabilities for code vectors.
        Dim 6 (intent drift):       DB query for symbols with intent text +
                                    stored code vector → embed intent on-demand
                                    → cosine distance.

        Returns (semantic_landscape, intent_drift).
        """
        qdrant = getattr(self._ctx, "qdrant_service", None)
        if qdrant is None:
            logger.warning(
                "QdrantService not available — skipping vector dimensions 2+6"
            )
            return {}, {}

        logger.info("🔮 [Dim 2] Scrolling core_capabilities...")

        try:
            code_points = await qdrant.scroll_all_points(
                with_payload=True,
                with_vectors=False,  # payload only for landscape
                collection_name="core_capabilities",
            )
        except Exception as e:
            logger.warning("core_capabilities scroll failed: %s", e)
            code_points = []

        logger.info("   Found %d code vectors", len(code_points))

        semantic_landscape = self._build_semantic_landscape(code_points)
        intent_drift = await self._compute_intent_drift(session, qdrant)
        return semantic_landscape, intent_drift

    # ID: sa-compute-intent-drift
    async def _compute_intent_drift(
        self,
        session: AsyncSession,
        qdrant: Any,
        sample_limit: int = 100,
    ) -> dict[str, Any]:
        """
        Dimension 6: Where does meaning diverge from code?

        Algorithm:
            1. Query DB for symbols that have BOTH intent text AND a vector_id
            2. Fetch code vector from Qdrant by vector_id
            3. Embed intent text via CognitiveService
            4. Cosine distance → drift score

        Samples up to `sample_limit` symbols (sorted by symbol_path for stability).
        Drift > 0.3 = high concern. Drift > 0.6 = critical misalignment.
        """
        from sqlalchemy import text

        logger.info("🧭 [Dim 6] Computing intent drift (DB + embeddings)...")

        # Step 1: symbols with both intent and a code vector
        try:
            result = await session.execute(
                text(
                    """
                    SELECT
                        s.symbol_path,
                        s.intent,
                        l.vector_id::text
                    FROM core.symbols s
                    JOIN core.symbol_vector_links l ON s.id = l.symbol_id
                    WHERE s.intent IS NOT NULL
                      AND s.intent != ''
                      AND l.vector_id IS NOT NULL
                    ORDER BY s.symbol_path
                    LIMIT :limit
                """
                ),
                {"limit": sample_limit},
            )
            candidates = result.mappings().all()
        except Exception as e:
            logger.warning("Intent drift DB query failed: %s", e)
            return {}

        if not candidates:
            logger.info("   [Dim 6] No candidates (symbols need both intent + vector)")
            return {
                "symbols_with_both_vectors": 0,
                "high_drift_count": 0,
                "critical_drift_count": 0,
                "top_drifted_symbols": [],
                "well_aligned_count": 0,
                "note": "No symbols have both intent text and code vectors yet",
            }

        logger.info(
            "   [Dim 6] Sampling %d symbols for drift computation", len(candidates)
        )

        # Step 2 + 3: fetch code vector, embed intent, compute drift
        drift_scores: list[dict[str, Any]] = []

        for row in candidates:
            symbol_path = row["symbol_path"]
            intent_text = row["intent"]
            vector_id = row["vector_id"]

            try:
                code_vec = await qdrant.get_vector_by_id(vector_id)
            except Exception:
                continue  # vector missing or deleted

            try:
                intent_vec = await self._cognitive.get_embedding_for_code(intent_text)
            except Exception:
                continue

            if not code_vec or not intent_vec:
                continue

            similarity = _cosine_similarity(code_vec, intent_vec)
            drift_scores.append(
                {
                    "symbol": symbol_path,
                    "similarity": round(similarity, 4),
                    "drift": round(1.0 - similarity, 4),
                }
            )

        drift_scores.sort(key=lambda x: x["drift"], reverse=True)

        high_drift = [d for d in drift_scores if d["drift"] > 0.3]
        critical_drift = [d for d in drift_scores if d["drift"] > 0.6]

        logger.info(
            "   [Dim 6] %d computed, %d high drift (>0.3), %d critical (>0.6)",
            len(drift_scores),
            len(high_drift),
            len(critical_drift),
        )

        return {
            "symbols_sampled": len(drift_scores),
            "high_drift_count": len(high_drift),
            "critical_drift_count": len(critical_drift),
            "top_drifted_symbols": drift_scores[:10],
            "well_aligned_count": len([d for d in drift_scores if d["drift"] < 0.1]),
            "average_drift": (
                round(sum(d["drift"] for d in drift_scores) / len(drift_scores), 4)
                if drift_scores
                else 0.0
            ),
        }

    # ID: sa-build-semantic-landscape
    def _build_semantic_landscape(self, all_points: list) -> dict[str, Any]:
        """
        What concepts is CORE built from? (Dimension 2)

        Groups vectors by module and capability tags to reveal semantic clusters
        and identify which modules carry the most conceptual weight.
        """
        by_module: dict[str, int] = defaultdict(int)
        by_source_type: dict[str, int] = defaultdict(int)
        capability_counts: dict[str, int] = defaultdict(int)
        hotspot_files: dict[str, int] = defaultdict(int)

        for point in all_points:
            payload = getattr(point, "payload", None) or {}
            source_path = payload.get("source_path", "unknown")
            source_type = payload.get("source_type", "unknown")
            capability_tags = payload.get("capability_tags") or []

            parts = source_path.split("/")
            module = parts[1] if len(parts) > 2 and parts[0] == "src" else parts[0]

            by_module[module] += 1
            by_source_type[source_type] += 1
            hotspot_files[source_path] += 1
            for tag in capability_tags:
                capability_counts[tag] += 1

        top_hotspots = sorted(hotspot_files.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]
        top_capabilities = sorted(
            capability_counts.items(), key=lambda x: x[1], reverse=True
        )[:15]

        logger.info(
            "   [Dim 2] %d modules, %d capability types, %d hotspot files",
            len(by_module),
            len(capability_counts),
            len(hotspot_files),
        )

        return {
            "total_vectors": len(all_points),
            "by_module": dict(
                sorted(by_module.items(), key=lambda x: x[1], reverse=True)
            ),
            "by_source_type": dict(by_source_type),
            "top_hotspot_files": [
                {"file": f, "vector_count": c} for f, c in top_hotspots
            ],
            "top_capability_clusters": [
                {"capability": cap, "count": cnt} for cap, cnt in top_capabilities
            ],
        }

    # -------------------------------------------------------------------------
    # Dimension 3: Knowledge Gaps
    # -------------------------------------------------------------------------

    # ID: sa-gather-knowledge-gaps
    async def _gather_knowledge_gaps(self, session: AsyncSession) -> dict[str, Any]:
        """
        Where is CORE blind to itself? (Dimension 3)

        Finds symbols with missing intent, signature, or vector coverage.
        You can't govern what you can't see.
        """
        from sqlalchemy import text

        logger.info("🕳️  [Dim 3] Analysing knowledge gaps...")

        try:
            result = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE intent IS NULL OR intent = '')
                                                            AS no_intent,
                        COUNT(*) FILTER (WHERE ast_signature IS NULL
                                         OR ast_signature = 'pending')
                                                            AS no_signature,
                        COUNT(*) FILTER (WHERE id NOT IN (
                            SELECT DISTINCT symbol_id::uuid
                            FROM core.symbol_vector_links
                        ))                                  AS no_vector,
                        COUNT(*) FILTER (
                            WHERE (intent IS NULL OR intent = '')
                            AND (ast_signature IS NULL OR ast_signature = 'pending')
                        )                                   AS no_intent_no_sig,
                        COUNT(*) FILTER (
                            WHERE (intent IS NULL OR intent = '')
                            AND id NOT IN (
                                SELECT DISTINCT symbol_id::uuid
                                FROM core.symbol_vector_links
                            )
                        )                                   AS no_intent_no_vector
                    FROM core.symbols
                    WHERE kind IN ('function', 'class', 'method')
                """
                )
            )
            gaps = dict(result.mappings().one())

            # Worst modules by intent coverage gap
            module_result = await session.execute(
                text(
                    """
                    SELECT
                        split_part(file_path, '/', 2)           AS module,
                        COUNT(*)                                 AS total,
                        COUNT(*) FILTER (WHERE intent IS NULL
                                         OR intent = '')         AS missing_intent,
                        ROUND(
                            100.0 * COUNT(*) FILTER (
                                WHERE intent IS NOT NULL AND intent != ''
                            ) / NULLIF(COUNT(*), 0)
                        )                                        AS intent_pct
                    FROM core.symbols
                    WHERE kind IN ('function', 'class', 'method')
                    GROUP BY split_part(file_path, '/', 2)
                    ORDER BY missing_intent DESC
                    LIMIT 10
                """
                )
            )
            gaps["worst_modules_by_intent_gap"] = [
                dict(r) for r in module_result.mappings().all()
            ]

            logger.info(
                "   [Dim 3] no_intent=%d, no_vector=%d, no_signature=%d",
                gaps.get("no_intent", 0),
                gaps.get("no_vector", 0),
                gaps.get("no_signature", 0),
            )
            return gaps

        except Exception as e:
            logger.warning("Knowledge gaps query failed: %s", e)
            return {}

    # -------------------------------------------------------------------------
    # Dimension 4: Structural Health
    # -------------------------------------------------------------------------

    # ID: sa-gather-structural-health
    async def _gather_structural_health(self, session: AsyncSession) -> dict[str, Any]:
        """
        What does CORE contain? (Dimension 4)

        Summary of the knowledge graph — symbol counts, coverage, layer balance.
        """
        from sqlalchemy import text

        logger.info("🏗️  [Dim 4] Analysing structural health...")

        try:
            result = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*)                                           AS total_symbols,
                        COUNT(*) FILTER (WHERE kind = 'class')            AS classes,
                        COUNT(*) FILTER (WHERE kind = 'function')         AS functions,
                        COUNT(*) FILTER (WHERE kind = 'method')           AS methods,
                        COUNT(*) FILTER (WHERE intent IS NOT NULL
                                         AND intent != '')                AS with_intent,
                        COUNT(*) FILTER (WHERE ast_signature IS NOT NULL
                                         AND ast_signature != 'pending')  AS with_signature,
                        ROUND(100.0 * COUNT(*) FILTER (
                            WHERE intent IS NOT NULL AND intent != ''
                        ) / NULLIF(COUNT(*), 0))                          AS intent_pct,
                        ROUND(100.0 * COUNT(*) FILTER (
                            WHERE ast_signature IS NOT NULL
                            AND ast_signature != 'pending'
                        ) / NULLIF(COUNT(*), 0))                          AS signature_pct
                    FROM core.symbols
                """
                )
            )
            health = dict(result.mappings().one())

            layer_result = await session.execute(
                text(
                    """
                    SELECT
                        split_part(file_path, '/', 2) AS layer,
                        COUNT(*)                      AS symbol_count
                    FROM core.symbols
                    GROUP BY split_part(file_path, '/', 2)
                    ORDER BY symbol_count DESC
                    LIMIT 8
                """
                )
            )
            health["layer_distribution"] = [
                dict(r) for r in layer_result.mappings().all()
            ]

            logger.info(
                "   [Dim 4] %d symbols, intent=%s%%, signature=%s%%",
                health.get("total_symbols", 0),
                health.get("intent_pct", 0),
                health.get("signature_pct", 0),
            )
            return health

        except Exception as e:
            logger.warning("Structural health query failed: %s", e)
            return {}

    # -------------------------------------------------------------------------
    # Dimension 5: Change Context
    # -------------------------------------------------------------------------

    # ID: sa-gather-change-context
    def _gather_change_context(self, n_commits: int = 15) -> dict[str, Any]:
        """
        What is CORE becoming? (Dimension 5)

        Recent git history reveals which parts of the system are actively
        evolving and provides causal context for audit findings.
        """
        logger.info("📜 [Dim 5] Reading change context...")

        try:
            repo_path = self._ctx.git_service.repo_path

            log = subprocess.run(
                ["git", "log", f"-{n_commits}", "--oneline", "--no-merges"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            stat = subprocess.run(
                ["git", "diff", "--stat", "HEAD~5", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            files_changed = subprocess.run(
                ["git", "log", "--name-only", "--pretty=format:", "-20"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            file_frequency: dict[str, int] = defaultdict(int)
            for line in files_changed.stdout.splitlines():
                line = line.strip()
                if line and line.endswith(".py"):
                    file_frequency[line] += 1

            hot_files = sorted(
                file_frequency.items(), key=lambda x: x[1], reverse=True
            )[:10]

            return {
                "recent_commits": log.stdout.strip().splitlines(),
                "recent_changes_stat": stat.stdout.strip(),
                "most_changed_files": [
                    {"file": f, "change_count": c} for f, c in hot_files
                ],
            }
        except Exception as e:
            logger.warning("Change context failed: %s", e)
            return {}

    # -------------------------------------------------------------------------
    # Constitution Summary (supporting data for the LLM)
    # -------------------------------------------------------------------------

    # ID: sa-gather-constitution-summary
    def _gather_constitution_summary(self) -> dict[str, Any]:
        """Read constitutional structure from .intent/ via IntentRepository."""
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        try:
            repo = get_intent_repository()
            repo.initialize()
            policies = list(repo.list_policies())
            return {
                "policy_count": len(policies),
                "policy_ids": [p.policy_id for p in policies[:20]],
            }
        except Exception as e:
            logger.warning("Constitution summary failed: %s", e)
            return {}
