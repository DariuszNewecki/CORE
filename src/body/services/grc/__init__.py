# src/body/services/grc/__init__.py
"""GRC (Governance, Risk, Compliance) gap-analysis — the Scenario-4 service.

Runs a maintained catalog of checkable compliance requirements (the Intent)
against a customer's document corpus (the Artifact) and returns a gap report
where every finding carries its ADR-113 evidence class — proven / judged /
attested. This is the hosted-service shape: it drives the same constitutional
engine CORE runs on itself, decoupling the requirements catalog from the corpus
location, rather than installing CORE inside the customer's repository.
"""

from __future__ import annotations

from body.services.grc.gap_analysis_service import (
    GRCGapAnalysisService,
    RequirementResult,
    build_framework_descriptor,
    load_catalog,
    load_catalog_meta,
    load_demo_catalog,
)


__all__ = [
    "GRCGapAnalysisService",
    "RequirementResult",
    "build_framework_descriptor",
    "load_catalog",
    "load_catalog_meta",
    "load_demo_catalog",
]
