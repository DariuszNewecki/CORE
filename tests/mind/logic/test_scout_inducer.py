"""Tests for ScoutInducer — the ADR-119 D3 rule induction Mind component.

Source: src/mind/logic/scout_inducer.py · Symbol: ScoutInducer

Mirrors the GRCApplicabilityGate test approach: the inducer loads its
PromptModel from disk in __init__, so each test substitutes ._prompt_model
with a MagicMock exposing an AsyncMock invoke(). The central invariant is
honest degradation — any failure returns an empty list, never a crash or a
silent non-empty result.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, Mock

from mind.logic.scout_inducer import ScoutInducer


def _inducer(*, return_value=None, side_effect=None):
    kwargs: dict = {}
    if return_value is not None:
        kwargs["return_value"] = return_value
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    invoke_mock = AsyncMock(**kwargs)
    inducer = ScoutInducer(llm_client=Mock())
    inducer._prompt_model = MagicMock(invoke=invoke_mock)
    return inducer, invoke_mock


_SIGNALS = "Python files total: 20\nprint() calls: 5"

_GOOD_CANDIDATE = {
    "rule_id": "scout.docstrings",
    "statement": "Public functions MUST have a docstring.",
    "enforcement": "reporting",
    "rationale": "~50% of public symbols lack docstrings.",
    "engine": "ast_gate",
    "params": {"check_type": "docstrings_present"},
    "scope": {"applies_to": ["src/**/*.py"], "excludes": []},
    "evidence_sample": "",
    "ramp_note": "",
}


async def test_valid_candidates_returned():
    payload = json.dumps({"candidates": [_GOOD_CANDIDATE]})
    inducer, invoke_mock = _inducer(return_value=payload)

    result = await inducer.propose(_SIGNALS)

    assert len(result) == 1
    assert result[0]["rule_id"] == "scout.docstrings"
    invoke_mock.assert_awaited_once()


async def test_multiple_candidates_all_returned():
    second = {**_GOOD_CANDIDATE, "rule_id": "scout.no_print"}
    payload = json.dumps({"candidates": [_GOOD_CANDIDATE, second]})
    inducer, _ = _inducer(return_value=payload)

    result = await inducer.propose(_SIGNALS)

    assert len(result) == 2
    assert {c["rule_id"] for c in result} == {"scout.docstrings", "scout.no_print"}


async def test_llm_failure_returns_empty_list():
    """Any AI exception degrades to [] — callers must handle the fallback path."""
    inducer, _ = _inducer(side_effect=Exception("connection reset"))

    result = await inducer.propose(_SIGNALS)

    assert result == []


async def test_invalid_json_returns_empty_list():
    inducer, _ = _inducer(return_value="not json at all")

    result = await inducer.propose(_SIGNALS)

    assert result == []


async def test_missing_candidates_key_returns_empty_list():
    """Response with wrong shape (not a 'candidates' array) degrades to []."""
    inducer, _ = _inducer(return_value=json.dumps({"rules": [_GOOD_CANDIDATE]}))

    result = await inducer.propose(_SIGNALS)

    assert result == []


async def test_candidates_without_rule_id_are_dropped():
    """Candidates missing rule_id are filtered out — partial results are still honest."""
    bad = {**_GOOD_CANDIDATE}
    del bad["rule_id"]
    payload = json.dumps({"candidates": [_GOOD_CANDIDATE, bad]})
    inducer, _ = _inducer(return_value=payload)

    result = await inducer.propose(_SIGNALS)

    assert len(result) == 1
    assert result[0]["rule_id"] == "scout.docstrings"


async def test_empty_candidates_array_is_valid():
    """An empty array is a legitimate LLM response — no rules observable."""
    inducer, _ = _inducer(return_value=json.dumps({"candidates": []}))

    result = await inducer.propose(_SIGNALS)

    assert result == []


async def test_json_fenced_response_is_parsed():
    """extract_json handles markdown-fenced responses from some models."""
    payload = "```json\n" + json.dumps({"candidates": [_GOOD_CANDIDATE]}) + "\n```"
    inducer, _ = _inducer(return_value=payload)

    result = await inducer.propose(_SIGNALS)

    assert len(result) == 1
