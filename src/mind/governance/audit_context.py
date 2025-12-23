# src/mind/governance/audit_context.py

"""
AuditorContext: central view of constitutional artifacts and the knowledge graph
for governance checks and audits.

CONSTITUTIONAL COMPLIANCE:
- Uses IntentRepository for ALL .intent/ access (Mind-Body-Will boundary enforcement)
- Loads Knowledge Graph from Database (SSOT) via KnowledgeService
- NO direct filesystem access to .intent/ subdirectories
- Exposes governance resources via policies dict (loaded from IntentRepository)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.config import settings
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger
from shared.models import AuditFinding
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ID: 55a77b97-fc08-4b0c-b818-97b1158343e9
class AuditorContext:
    """
    Provides access to '.intent' artifacts and the in-memory knowledge graph.

    CONSTITUTIONAL BOUNDARY ENFORCEMENT:
    - All .intent/ access goes through IntentRepository
    - No direct filesystem paths to .intent/ subdirectories
    - Policies loaded via IntentRepository APIs only
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.meta: dict[str, Any] = settings._meta_config
        self.paths = PathResolver(repo_path, self.meta)
        self.src_dir = self.paths.repo_root / "src"
        self.intent_path = self.paths.intent_root
        self.last_findings: list[AuditFinding] = []

        # Governance resources loaded via IntentRepository (CONSTITUTIONAL)
        self.policies: dict[str, Any] = self._load_governance_resources()

        # Knowledge graph state (loaded from database)
        self.knowledge_graph: dict[str, Any] = {"symbols": {}}
        self.symbols_list: list = []
        self.symbols_map: dict = {}

        logger.debug("AuditorContext initialized for %s", self.repo_path)

    @property
    # ID: e6f262c9-0852-4d65-8fc7-c0a03808b3b7
    def mind_path(self) -> Path:
        """
        Legacy accessor - DEPRECATED.
        Returns intent_root for backward compatibility.
        New code should use IntentRepository APIs.
        """
        logger.warning(
            "AuditorContext.mind_path is deprecated. Use IntentRepository instead."
        )
        return self.intent_path

    @property
    # ID: 3b95fd8e-69e9-4909-bbbd-bfc2f8c31c1e
    def charter_path(self) -> Path:
        """
        Legacy accessor - DEPRECATED.
        Returns intent_root for backward compatibility.
        New code should use IntentRepository APIs.
        """
        logger.warning(
            "AuditorContext.charter_path is deprecated. Use IntentRepository instead."
        )
        return self.intent_path

    # ID: 090d1c13-3389-4f4c-81d0-eadf1c3259b2
    async def load_knowledge_graph(self) -> None:
        """
        Load the knowledge graph from the Database (SSOT).
        """
        logger.info(
            "Loading knowledge graph from database (SSOT) for %s...", self.repo_path
        )
        try:
            knowledge_service = KnowledgeService(self.repo_path)
            self.knowledge_graph = await knowledge_service.get_graph()
            self.symbols_map = self.knowledge_graph.get("symbols", {})
            self.symbols_list = list(self.symbols_map.values())
            logger.info(
                "Loaded knowledge graph with %s symbols from database.",
                len(self.symbols_list),
            )
            self._save_knowledge_graph_artifact()
        except Exception as e:
            logger.error("Failed to load knowledge graph from DB: %s", e)
            self.knowledge_graph = {"symbols": {}}

    def _save_knowledge_graph_artifact(self) -> None:
        """Save knowledge graph to reports/ for debugging."""
        import json

        reports_dir = self.paths.reports_dir
        reports_dir.mkdir(exist_ok=True)
        artifact_path = reports_dir / "knowledge_graph.json"
        try:
            with open(artifact_path, "w", encoding="utf-8") as f:
                json.dump(self.knowledge_graph, f, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to save knowledge graph artifact: %s", e)

    def _load_governance_resources(self) -> dict[str, Any]:
        """
        Load governance resources via IntentRepository (CONSTITUTIONAL).

        This is the ONLY way AuditorContext accesses .intent/ files.
        All filesystem navigation happens inside IntentRepository.

        Returns:
            Dict mapping various keys to policy documents:
            - canonical keys: "policies/architecture/agent_governance"
            - policy_id from document: "standard_architecture_agent_governance"
            - stem (legacy): "agent_governance"
        """
        resources: dict[str, Any] = {}

        try:
            intent_repo = get_intent_repository()

            # Load all policies via repository
            for policy_ref in intent_repo.list_policies():
                try:
                    policy_data = intent_repo.load_document(policy_ref.path)

                    if not isinstance(policy_data, dict):
                        continue

                    # Canonical key (e.g., "policies/architecture/agent_governance")
                    resources[policy_ref.policy_id] = policy_data

                    # Stem for legacy callers (e.g., "agent_governance")
                    stem = Path(policy_ref.policy_id).stem
                    resources[stem] = policy_data

                    # Internal document ID if present
                    doc_id = policy_data.get("id")
                    if isinstance(doc_id, str) and doc_id:
                        resources[doc_id] = policy_data

                except Exception as e:
                    logger.debug(
                        "Failed to load policy %s: %s", policy_ref.policy_id, e
                    )

            logger.info(
                "Loaded %s governance resource(s) from IntentRepository",
                len(intent_repo.list_policies()),
            )

        except Exception as e:
            logger.error(
                "Failed to load governance resources via IntentRepository: %s", e
            )

        return resources

    @property
    # ID: 39d97b4e-5d44-4e43-8ccc-d194f851c62c
    def python_files(self) -> list[Path]:
        """Returns Python files ONLY from BODY (src/)."""
        paths: list[Path] = []
        if self.src_dir.exists():
            paths.extend(self.src_dir.rglob("*.py"))
        return list(paths)


__all__ = ["AuditorContext"]
