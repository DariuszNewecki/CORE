"""Tests for GRCJudgeEngine — the GRC semantic compliance judge.

Source: src/mind/logic/engines/grc_judge.py · Symbol: GRCJudgeEngine

Mirrors the llm_gate test approach: the engine loads its PromptModel from disk
in __init__, so each test substitutes ``._prompt_model`` with a MagicMock
exposing an AsyncMock ``invoke()``. ``self.llm`` is a bare Mock — verify()
forwards it to invoke(), which ignores it.

The GRC judge differs from llm_gate in framing: a "violation" is a *compliance
gap* (the document does not satisfy the requirement), and there is no ADR-044
DB verdict cache (the gap-analysis corpus has no DB session plumbed).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from mind.logic.engines.grc_judge import GRCJudgeEngine
from shared.path_resolver import PathResolver


_REPO_ROOT = Path("/opt/dev/CORE")


@pytest.fixture
def path_resolver():
    return PathResolver(repo_root=_REPO_ROOT)


@pytest.fixture
def tmp_doc():
    """Per-test document under var/tmp/ (CLAUDE.md prohibits /tmp/)."""
    repo_tmp = _REPO_ROOT / "var" / "tmp"
    repo_tmp.mkdir(parents=True, exist_ok=True)
    p = repo_tmp / f"grc_judge_test_{uuid.uuid4().hex}.md"
    yield p
    p.unlink(missing_ok=True)


def _engine(path_resolver, *, return_value=None, side_effect=None):
    kwargs = {}
    if return_value is not None:
        kwargs["return_value"] = return_value
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    invoke_mock = AsyncMock(**kwargs)
    engine = GRCJudgeEngine(path_resolver=path_resolver, llm_client=Mock())
    engine._prompt_model = MagicMock(invoke=invoke_mock)
    return engine, invoke_mock


@pytest.mark.asyncio
async def test_requirement_satisfied(path_resolver, tmp_doc):
    """violation=False → ok=True, no findings (the document satisfies it)."""
    engine, invoke_mock = _engine(
        path_resolver,
        return_value=json.dumps(
            {"violation": False, "reasoning": "MFA required for remote access", "finding": None}
        ),
    )
    tmp_doc.write_text("Remote access requires MFA.", encoding="utf-8")
    params = {"instruction": "Requires MFA for remote access?", "rationale": "NIST 3.5.3"}

    result = await engine.verify(tmp_doc, params)

    assert result.ok
    assert result.message == "Requirement satisfied by the document corpus."
    assert result.violations == []
    assert result.engine_id == "grc_judge"
    invoke_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_compliance_gap_with_finding(path_resolver, tmp_doc):
    """violation=True with a finding → ok=False, finding propagated as the gap."""
    engine, _ = _engine(
        path_resolver,
        return_value=json.dumps(
            {
                "violation": True,
                "reasoning": "Document is silent on MFA",
                "finding": "No MFA requirement for remote access",
            }
        ),
    )
    tmp_doc.write_text("Remote access is permitted.", encoding="utf-8")
    params = {"instruction": "Requires MFA for remote access?", "rationale": "NIST 3.5.3"}

    result = await engine.verify(tmp_doc, params)

    assert not result.ok
    assert result.message == "Compliance gap: No MFA requirement for remote access"
    assert result.violations == ["No MFA requirement for remote access"]
    assert result.engine_id == "grc_judge"


@pytest.mark.asyncio
async def test_gap_falls_back_to_reasoning_when_no_finding(path_resolver, tmp_doc):
    """violation=True but finding=None → reasoning becomes the gap text."""
    engine, _ = _engine(
        path_resolver,
        return_value=json.dumps(
            {"violation": True, "reasoning": "Silent on MFA", "finding": None}
        ),
    )
    tmp_doc.write_text("Remote access is permitted.", encoding="utf-8")
    params = {"instruction": "Requires MFA?", "rationale": "NIST 3.5.3"}

    result = await engine.verify(tmp_doc, params)

    assert not result.ok
    assert result.message == "Compliance gap: Silent on MFA"
    assert result.violations == ["Silent on MFA"]


@pytest.mark.asyncio
async def test_file_read_error_skips_invoke(path_resolver):
    """File read fails → IO Error result, the prompt is never invoked."""
    engine, invoke_mock = _engine(path_resolver)
    params = {"instruction": "Requires MFA?", "rationale": "NIST 3.5.3"}

    result = await engine.verify(Path("/non/existent/doc.md"), params)

    assert not result.ok
    assert "IO Error" in result.message
    assert result.violations == []
    invoke_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_ai_failure_is_unavailable_not_gap(path_resolver, tmp_doc):
    """invoke raises → ENFORCEMENT_UNAVAILABLE with the shared offline marker
    (so rule_executor aggregates it rather than counting a false gap)."""
    engine, _ = _engine(path_resolver, side_effect=Exception("API timeout"))
    tmp_doc.write_text("anything", encoding="utf-8")
    params = {"instruction": "Requires MFA?", "rationale": "NIST 3.5.3"}

    result = await engine.verify(tmp_doc, params)

    assert not result.ok
    assert "ENFORCEMENT_UNAVAILABLE" in result.message
    assert result.violations == ["SYSTEM_ERROR_AI_OFFLINE"]


@pytest.mark.asyncio
async def test_invalid_json_is_unavailable(path_resolver, tmp_doc):
    """Non-JSON response → same UNAVAILABLE path (never a silent pass)."""
    engine, _ = _engine(path_resolver, return_value="not json")
    tmp_doc.write_text("anything", encoding="utf-8")
    params = {"instruction": "Requires MFA?", "rationale": "NIST 3.5.3"}

    result = await engine.verify(tmp_doc, params)

    assert not result.ok
    assert result.violations == ["SYSTEM_ERROR_AI_OFFLINE"]


def test_evidence_class_is_judged(path_resolver):
    """ADR-113: the GRC judge establishes a JUDGED verdict, never PROVEN."""
    from shared.models import EvidenceClass

    engine = GRCJudgeEngine(path_resolver=path_resolver, llm_client=Mock())
    assert engine.evidence_class is EvidenceClass.JUDGED
    assert engine.engine_id == "grc_judge"


def test_get_corpus_clients_none_without_injected_embedder(path_resolver):
    """_get_corpus_clients returns None when no embedding_client was injected."""
    engine = GRCJudgeEngine(path_resolver=path_resolver, llm_client=Mock())
    assert engine._embedder is None
    assert engine._get_corpus_clients() is None


def test_get_corpus_clients_uses_injected_embedder(path_resolver):
    """_get_corpus_clients returns (qdrant, embedder) when embedder was injected."""
    from unittest.mock import patch

    mock_embedder = MagicMock()
    mock_qdrant_cls = MagicMock()
    mock_qdrant_instance = MagicMock()
    mock_qdrant_cls.return_value = mock_qdrant_instance

    engine = GRCJudgeEngine(
        path_resolver=path_resolver,
        llm_client=Mock(),
        embedding_client=mock_embedder,
    )
    assert engine._embedder is mock_embedder

    with patch(
        "mind.logic.engines.grc_judge.QdrantService",
        mock_qdrant_cls,
        create=True,
    ):
        pass  # QdrantService is imported inside the method; patch via import target
    with patch(
        "shared.infrastructure.clients.qdrant_client.QdrantService",
        mock_qdrant_cls,
    ):
        result = engine._get_corpus_clients()
    # With embedder injected, the method proceeds to init Qdrant
    assert result is not None
    _, returned_embedder = result
    assert returned_embedder is mock_embedder
