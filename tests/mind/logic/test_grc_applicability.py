"""Tests for GRCApplicabilityGate — the ADR-118 D2 corpus-domain fit gate.

Source: src/mind/logic/grc_applicability.py · Symbol: GRCApplicabilityGate

Mirrors the grc_judge test approach: the gate loads its PromptModel from disk in
__init__, so each test substitutes ``._prompt_model`` with a MagicMock exposing
an AsyncMock ``invoke()``. The central invariant is honest degradation — every
failure path resolves to ``uncertain``, never a silent ``in_scope`` (CORE MUST
NOT silently assume domain fit).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from mind.logic.grc_applicability import GRCApplicabilityGate
from shared.models import Applicability, EvidenceClass


def _gate(*, return_value=None, side_effect=None):
    kwargs = {}
    if return_value is not None:
        kwargs["return_value"] = return_value
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    invoke_mock = AsyncMock(**kwargs)
    gate = GRCApplicabilityGate(llm_client=Mock())
    gate._prompt_model = MagicMock(invoke=invoke_mock)
    return gate, invoke_mock


async def _assess(gate):
    return await gate.assess(
        framework_id="nist_800_171",
        framework_descriptor="Title: NIST SP 800-171\nAuthority: NIST",
        corpus_excerpt="### policy.md\nAll remote access requires MFA.",
    )


@pytest.mark.asyncio
async def test_in_scope_parsed_with_domains():
    gate, invoke_mock = _gate(
        return_value=json.dumps(
            {
                "applicability": "in_scope",
                "detected_domains": "information security, access control",
                "reasoning": "Corpus is about IT security controls.",
            }
        ),
    )
    result = await _assess(gate)

    assert result.applicability is Applicability.IN_SCOPE
    assert result.framework_id == "nist_800_171"
    assert result.detected_domains == ["information security", "access control"]
    assert result.rationale == "Corpus is about IT security controls."
    assert result.evidence_class is EvidenceClass.JUDGED
    assert result.requires_confirmation is False
    invoke_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_out_of_scope_requires_confirmation():
    gate, _ = _gate(
        return_value=json.dumps(
            {
                "applicability": "out_of_scope",
                "detected_domains": "facilities management",
                "reasoning": "Corpus is about building maintenance, not infosec.",
            }
        ),
    )
    result = await _assess(gate)

    assert result.applicability is Applicability.OUT_OF_SCOPE
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_domains_as_list_normalized():
    gate, _ = _gate(
        return_value=json.dumps(
            {
                "applicability": "uncertain",
                "detected_domains": ["security", "  ", "privacy"],
                "reasoning": "Mixed corpus.",
            }
        ),
    )
    result = await _assess(gate)

    assert result.applicability is Applicability.UNCERTAIN
    assert result.detected_domains == ["security", "privacy"]


@pytest.mark.asyncio
async def test_unknown_label_fails_closed_to_uncertain():
    """An out-of-vocabulary applicability label degrades to uncertain, never
    to a silent in_scope (fail-closed, ADR-118 D2)."""
    gate, _ = _gate(
        return_value=json.dumps(
            {"applicability": "probably_yes", "detected_domains": "x", "reasoning": "y"}
        ),
    )
    result = await _assess(gate)
    assert result.applicability is Applicability.UNCERTAIN


@pytest.mark.asyncio
async def test_ai_failure_is_uncertain_not_in_scope():
    gate, _ = _gate(side_effect=Exception("API timeout"))
    result = await _assess(gate)
    assert result.applicability is Applicability.UNCERTAIN
    assert "could not be established" in result.rationale


@pytest.mark.asyncio
async def test_invalid_json_is_uncertain():
    gate, _ = _gate(return_value="not json at all")
    result = await _assess(gate)
    assert result.applicability is Applicability.UNCERTAIN


def test_evidence_class_is_judged():
    gate = GRCApplicabilityGate(llm_client=Mock())
    assert gate.evidence_class is EvidenceClass.JUDGED
