# src/body/atomic/document/gap_analysis_action.py
"""
document.run.gap_analysis — domain-agnostic document corpus gap-analysis action.

First atomic action carrying artifact_types: [document_corpus] (ADR-121 D4).
Triggers ADR-092-A: action_supported_by_declaration rule ships alongside this
action. Wraps DocumentCorpusAnalysisService; always read-only against the corpus
(CORE-BYOR §5 parameter 3). The write flag controls report-file output only.

CONSTITUTIONAL ALIGNMENT:
- Category: CHECK (read-only audit; no corpus mutations)
- Impact:   safe (reading files + optionally writing a report; no code changes)
- Policy:   document.policy.analysis_scope
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from body.atomic.registry import ActionCategory, register_action
from body.services.grc.catalog_resolver import discover_catalogs
from body.services.grc.gap_analysis_service import (
    DocumentCorpusAnalysisService,
    load_catalog,
)
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


logger = getLogger(__name__)


@register_action(
    action_id="document.run.gap_analysis",
    description="Evaluate a document corpus against one or more requirements catalogs",
    category=ActionCategory.CHECK,
    policies=["document.policy.analysis_scope"],
    requires_db=False,
    requires_vectors=False,
)
@atomic_action(
    action_id="document.run.gap_analysis",
    intent="Evaluate a document corpus against requirements catalogs; report coverage gaps",
    impact=ActionImpact.READ_ONLY,
    policies=["document.policy.analysis_scope"],
)
# ID: f4c23b1d-a3ef-4b7d-bcdc-d6d735701bbb
async def action_run_gap_analysis(
    corpus_root: str,
    catalog_names: list[str] | None = None,
    catalog_root: str | None = None,
    write: bool = False,
    core_context: Any = None,
    **kwargs: Any,
) -> ActionResult:
    """Evaluate a document corpus against one or more requirements catalogs.

    Args:
        corpus_root:   Path to the document library (the Artifact). Relative
                       paths resolve from repo root.
        catalog_names: Catalogs to run. None/empty runs all available catalogs
                       at catalog_root (ADR-121 D3).
        catalog_root:  Override the catalog corpus root. None uses the default
                       grc-catalogs/ root (backward-compatible for GRC projects).
        write:         When True, write a YAML report to
                       var/reports/corpus/<slug>_<catalog>_<ts>.yaml.
                       The corpus itself is never modified regardless of this flag.
    """
    start = time.monotonic()

    resolved_corpus = Path(corpus_root)
    if not resolved_corpus.is_absolute():
        if core_context is None:
            raise ValueError(
                "corpus_root is a relative path but no core_context was injected. "
                "Pass an absolute corpus_root or invoke via ActionExecutor."
            )
        resolved_corpus = core_context.file_handler.repo_path / corpus_root

    resolved_catalog_root: Path | None = Path(catalog_root) if catalog_root else None

    available = discover_catalogs(resolved_catalog_root)
    if catalog_names:
        active = {n: p for n, p in available.items() if n in catalog_names}
    else:
        active = available

    if not active:
        elapsed = time.monotonic() - start
        return ActionResult(
            action_id="document.run.gap_analysis",
            ok=False,
            data={
                "corpus_root": str(resolved_corpus),
                "catalog_root": str(resolved_catalog_root)
                if resolved_catalog_root
                else "",
                "error": "No catalogs available at the configured catalog_root.",
            },
            duration_sec=elapsed,
        )

    service = DocumentCorpusAnalysisService()

    totals: dict[str, int] = {
        "total_requirements": 0,
        "satisfied": 0,
        "deficient": 0,
        "not_covered": 0,
        "covered_unauthoritatively": 0,
        "not_applicable": 0,
        "needs_human": 0,
        "unavailable": 0,
    }
    catalogs_run: list[str] = []

    for catalog_name in active:
        try:
            rules = load_catalog(catalog_name, catalog_root=resolved_catalog_root)
            verdicts = await service.run(resolved_corpus, rules)
        except Exception as exc:
            logger.error(
                "document.run.gap_analysis: error running catalog %r: %s",
                catalog_name,
                exc,
                exc_info=True,
            )
            continue

        catalogs_run.append(catalog_name)
        totals["total_requirements"] += len(verdicts)
        for v in verdicts:
            key = v.status.value
            if key in totals:
                totals[key] += 1

        if write:
            if core_context is None:
                raise ValueError(
                    "write=True requires core_context to be injected. "
                    "Invoke via ActionExecutor."
                )
            _write_report(
                resolved_corpus,
                catalog_name,
                verdicts,
                resolved_catalog_root,
                core_context.file_handler,
            )

    elapsed = time.monotonic() - start
    return ActionResult(
        action_id="document.run.gap_analysis",
        ok=True,
        data={
            "corpus_root": str(resolved_corpus),
            "catalog_root": str(resolved_catalog_root) if resolved_catalog_root else "",
            "catalogs_run": catalogs_run,
            **totals,
        },
        impact=ActionImpact.READ_ONLY,
        duration_sec=elapsed,
    )


def _write_report(
    corpus_root: Path,
    catalog_name: str,
    verdicts: list[Any],
    catalog_root: Path | None,
    file_handler: Any,
) -> None:
    """Write gap-analysis verdicts to var/reports/corpus/ as YAML."""
    import yaml

    from shared.path_resolver import PathResolver

    slug = corpus_root.name or "corpus"
    ts = int(time.time())
    resolver = PathResolver.from_repo(file_handler.repo_path)
    reports_sub = resolver.reports_dir.relative_to(resolver.var_dir)
    rel_path = f"{reports_sub}/corpus/{slug}_{catalog_name}_{ts}.yaml"

    payload = {
        "catalog": catalog_name,
        "catalog_root": str(catalog_root) if catalog_root else "",
        "corpus_root": str(corpus_root),
        "verdicts": [
            {
                "requirement_id": v.requirement_id,
                "status": v.status.value,
                "evidence_class": v.evidence_class.value,
                "rationale": v.rationale or "",
                "statement": v.statement or "",
            }
            for v in verdicts
        ],
    }
    file_handler.write_runtime_text(rel_path, yaml.dump(payload, allow_unicode=True))
    logger.info("document.run.gap_analysis: report written to var/%s", rel_path)
