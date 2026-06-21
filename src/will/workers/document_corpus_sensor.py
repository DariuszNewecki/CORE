# src/will/workers/document_corpus_sensor.py
"""
DocumentCorpusSensor — domain-agnostic governed document corpus sensor (ADR-121 D2).

Reads a document corpus against one or more requirements catalogs and posts
gap findings to the blackboard. Domain is expressed through catalog selection:
a GRC project configures catalog_names pointing at grc-catalogs/; any other
domain supplies its own catalog_root. The sensor is domain-agnostic; only the
catalog content is domain-specific.

Constitutional standing:
- Declaration:      .intent/workers/document_corpus_sensor.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none — reads corpus files via Body service (delegate)
- Approval:         false — findings are observations only
- Schedule:         max_interval=3600s (project may adjust)

LAYER: will/workers — sensing worker. Delegates all file I/O to
DocumentCorpusAnalysisService (Body) per `must_delegate_to_body`. No direct
filesystem writes. Posts blackboard findings only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.models.grc_verdict import RequirementStatus
from shared.workers.base import Worker


logger = getLogger(__name__)

_SUBJECT_ARTIFACT_TYPE = "document_corpus"
_SUBJECT_NAMESPACE = "requirement"

# Gap statuses that warrant a blackboard finding (ADR-118 D3 / grc_verdict.py).
_GAP_STATUSES: frozenset[RequirementStatus] = frozenset(
    {
        RequirementStatus.DEFICIENT,
        RequirementStatus.NOT_COVERED,
        RequirementStatus.COVERED_UNAUTHORITATIVELY,
    }
)


# ID: a7f5af3c-e17e-47a0-9b3b-0bbcebdb35f8
class DocumentCorpusSensor(Worker):
    """
    Sensing worker. Evaluates a document corpus against requirements catalogs
    and posts gap findings to the blackboard (ADR-121 D2).

    Configuration is project-authored in mandate.scope (ADR-121 D3):
    - corpus_root: path to the document library (required; sensor no-ops without it)
    - catalog_root: override the catalog corpus root (default: grc-catalogs/)
    - catalog_names: list of catalog names to run (default: all available at root)

    One ``document_corpus::requirement::<requirement_id>`` finding per gap-status
    requirement per catalog per run. Satisfied, not_applicable, needs_human, and
    unavailable requirements are not posted (ADR-118 D3).
    """

    declaration_name = "document_corpus_sensor"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            declaration_name=kwargs.get("declaration_name", "document_corpus_sensor")
        )
        scope = self._declaration.get("mandate", {}).get("scope", {}) or {}
        self._corpus_root_str: str = scope.get("corpus_root", "") or ""
        self._catalog_root_str: str = scope.get("catalog_root", "") or ""
        self._catalog_names: list[str] = list(scope.get("catalog_names") or [])

    # ID: d67a1720-8253-4d97-b4b5-220ab3787a28
    async def run(self) -> None:
        """
        One detection cycle: load active catalogs, evaluate corpus, post findings.

        Heartbeat is posted unconditionally first so a downstream failure does
        not mark this worker as silent (ADR-041 / blackboard_shop_manager).
        """
        await self.post_heartbeat()

        if not self._corpus_root_str:
            logger.warning(
                "DocumentCorpusSensor: corpus_root not configured in "
                ".intent/workers/document_corpus_sensor.yaml mandate.scope; "
                "skipping scan. Set corpus_root to the project's document library path."
            )
            return

        corpus_root = self._resolve_corpus_root(self._corpus_root_str)
        catalog_root = self._resolve_catalog_root(self._catalog_root_str)

        active_catalogs = self._discover_active_catalogs(catalog_root)
        if not active_catalogs:
            logger.warning(
                "DocumentCorpusSensor: no catalogs available at %s; skipping scan.",
                catalog_root or "grc-catalogs/ (default)",
            )
            return

        from body.services.grc.gap_analysis_service import (
            DocumentCorpusAnalysisService,
            load_catalog,
        )

        service = DocumentCorpusAnalysisService()
        total_findings = 0

        for catalog_name in active_catalogs:
            try:
                rules = load_catalog(catalog_name, catalog_root=catalog_root)
                verdicts = await service.run(corpus_root, rules)
            except Exception as exc:
                logger.error(
                    "DocumentCorpusSensor: error running catalog %r: %s",
                    catalog_name,
                    exc,
                    exc_info=True,
                )
                continue

            for verdict in verdicts:
                if verdict.status not in _GAP_STATUSES:
                    continue
                subject = (
                    f"{_SUBJECT_ARTIFACT_TYPE}"
                    f"::{_SUBJECT_NAMESPACE}"
                    f"::{verdict.requirement_id}"
                )
                await self.post_artifact_finding(
                    artifact_type=_SUBJECT_ARTIFACT_TYPE,
                    sub_namespace=_SUBJECT_NAMESPACE,
                    identity_key_value=verdict.requirement_id,
                    payload={
                        "requirement_id": verdict.requirement_id,
                        "catalog": catalog_name,
                        "catalog_root": str(catalog_root) if catalog_root else "",
                        "status": verdict.status.value,
                        "evidence_class": verdict.evidence_class.value,
                        "corpus_root": str(corpus_root),
                        "evidence_count": len(verdict.evidence or []),
                        "rationale": verdict.rationale or "",
                    },
                )
                total_findings += 1

        logger.info(
            "DocumentCorpusSensor: scan complete — %d gap finding(s) posted "
            "across %d catalog(s)",
            total_findings,
            len(active_catalogs),
        )

    # ID: 0221f4f4-bbeb-45b0-b508-18b1a184e335
    def _resolve_corpus_root(self, corpus_root_str: str) -> Path:
        """Resolve corpus_root relative to repo_root when path is not absolute."""
        path = Path(corpus_root_str)
        if path.is_absolute():
            return path
        from shared.config import settings

        return settings.paths.repo_root / corpus_root_str

    # ID: d89c0f41-09e1-4e7d-ab65-1c4cf4798685
    def _resolve_catalog_root(self, catalog_root_str: str) -> Path | None:
        """Return explicit catalog_root or None (triggers default grc-catalogs/)."""
        if not catalog_root_str:
            return None
        return Path(catalog_root_str)

    # ID: 1e615fe3-ddc3-4f43-976f-73b8e044e08a
    def _discover_active_catalogs(self, catalog_root: Path | None) -> list[str]:
        """Return names of catalogs available at catalog_root.

        If catalog_names was configured in the mandate, filter to that subset.
        Otherwise return all available catalogs at the root (ADR-121 D3).
        """
        from body.services.grc.catalog_resolver import discover_catalogs

        available = discover_catalogs(catalog_root)
        if not available:
            return []

        if self._catalog_names:
            return [n for n in self._catalog_names if n in available]
        return list(available.keys())
