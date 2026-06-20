# src/body/services/grc/__init__.py
"""GRC (Governance, Risk, Compliance) gap-analysis — the Scenario-4 service.

Runs a maintained catalog of checkable compliance requirements (the Intent)
against a customer's document corpus (the Artifact) and returns one
``RequirementVerdict`` per requirement (ADR-118 D1) — the corpus-level outcome,
not per-document. Every verdict carries its ADR-113 evidence class — proven /
judged / attested — and localized evidence (D5).
"""

from __future__ import annotations

from body.services.grc.gap_analysis_service import (
    GRCGapAnalysisService,
    build_framework_descriptor,
    load_catalog,
    load_catalog_meta,
    load_demo_catalog,
)


__all__ = [
    "GRCGapAnalysisService",
    "build_framework_descriptor",
    "load_catalog",
    "load_catalog_meta",
    "load_demo_catalog",
]
