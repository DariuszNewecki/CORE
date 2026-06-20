"""Tests for the service-level applicability gate wiring (ADR-118 D2).

Source: src/body/services/grc/gap_analysis_service.py

Covers the honest-degradation paths that do not need an LLM (no client wired,
empty corpus) and the catalog-metadata → framework-descriptor helpers that feed
the gate's prompt.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from body.services.grc import (
    GRCGapAnalysisService,
    build_framework_descriptor,
)
from shared.models import Applicability, EvidenceClass


_REPO_TMP = Path("/opt/dev/CORE/var/tmp")


@pytest.fixture
def empty_corpus():
    """An empty corpus dir under var/tmp/ (CLAUDE.md prohibits /tmp/)."""
    _REPO_TMP.mkdir(parents=True, exist_ok=True)
    d = _REPO_TMP / f"grc_applic_corpus_{uuid.uuid4().hex}"
    d.mkdir()
    yield d
    d.rmdir()


@pytest.mark.asyncio
async def test_no_llm_client_degrades_to_uncertain(empty_corpus):
    """Without a judge wired, domain fit is unestablished — uncertain, not a
    silent in_scope."""
    service = GRCGapAnalysisService(llm_client=None)
    result = await service.assess_applicability(
        empty_corpus, framework_id="nist_800_171", framework_descriptor="NIST"
    )
    assert result.applicability is Applicability.UNCERTAIN
    assert result.evidence_class is EvidenceClass.JUDGED
    assert "No LLM judge" in result.rationale


@pytest.mark.asyncio
async def test_empty_corpus_degrades_to_uncertain(empty_corpus):
    """A client is wired but the corpus holds no readable text → uncertain,
    and the gate is never invoked (no text to judge)."""

    class _NeverCalled:
        async def invoke_semantic_check(self, *a, **k):  # pragma: no cover
            raise AssertionError("gate must not invoke with an empty corpus")

    service = GRCGapAnalysisService(llm_client=_NeverCalled())
    result = await service.assess_applicability(
        empty_corpus, framework_id="nist_800_171", framework_descriptor="NIST"
    )
    assert result.applicability is Applicability.UNCERTAIN
    assert "no readable text" in result.rationale.lower()


def test_build_framework_descriptor_uses_header_fields():
    descriptor = build_framework_descriptor(
        {
            "id": "nist_800_171",
            "title": "NIST SP 800-171 Rev. 2",
            "source": "Protecting CUI",
            "source_authority": "NIST",
            "source_revision": "Rev. 2",
        }
    )
    assert "Title: NIST SP 800-171 Rev. 2" in descriptor
    assert "Authority: NIST" in descriptor
    assert "Revision: Rev. 2" in descriptor


def test_build_framework_descriptor_falls_back_to_id_then_placeholder():
    assert "id-only" in build_framework_descriptor({"id": "id-only"})
    assert build_framework_descriptor({}) == "An unspecified compliance framework."
