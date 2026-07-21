# tests/mind/logic/engines/test_knowledge_gate__capability_taxonomy_whitelist.py

"""Unit tests for _check_capability_taxonomy_whitelist and its helpers.

Covers #820 Group A: the capability_taxonomy_whitelist check_type dispatched
by all four capability.taxonomy.* mappings (canonical_only,
no_ad_hoc_capabilities, roles_require_canonical_capabilities,
resources_provide_canonical_capabilities). Per CORE-Internal-Truthfulness,
a source that is not actually evaluated must never render as a clean pass —
these tests prove the ENFORCEMENT_FAILURE / real-violation / compliant
distinction holds for both source kinds (database_sources, artifact_sources).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from mind.logic.engines.knowledge_gate import KnowledgeGateEngine


_TAXONOMY_DOC = {
    "families": {
        "reasoning": {"capabilities": {"reasoning": {}, "analysis": {}}},
        "code": {"capabilities": {"code_generation": {}}},
    }
}
_CANONICAL = {"reasoning", "analysis", "code_generation"}


def _make_context(
    *,
    repo_path: Path,
    taxonomy_doc: dict | None = None,
    db_rows: list[tuple[Any, Any]] | None = None,
    db_session: Any = "unset",
    artifact_docs: list[tuple[Path, dict]] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.repo_path = repo_path
    intent_repo = MagicMock()
    if taxonomy_doc is not None:
        intent_repo.load_document = MagicMock(return_value=taxonomy_doc)
    else:
        intent_repo.load_document = MagicMock(
            side_effect=FileNotFoundError("no such taxonomy file")
        )
    intent_repo.iter_documents = MagicMock(return_value=iter(artifact_docs or []))
    ctx.intent_repo = intent_repo

    if db_session == "unset":
        db_session = None
        if db_rows is not None:
            session = AsyncMock()
            result = MagicMock()
            result.fetchall = MagicMock(return_value=db_rows)
            session.execute = AsyncMock(return_value=result)
            db_session = session
    ctx.db_session = db_session
    return ctx


def _engine() -> KnowledgeGateEngine:
    return KnowledgeGateEngine()


async def test_canonical_database_capabilities_pass_with_no_findings(tmp_path):
    ctx = _make_context(
        repo_path=tmp_path,
        taxonomy_doc=_TAXONOMY_DOC,
        db_rows=[("Coder", '["code_generation"]')],
    )
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
    )
    assert findings == []


async def test_non_canonical_database_value_is_reported_with_evidence(tmp_path):
    ctx = _make_context(
        repo_path=tmp_path,
        taxonomy_doc=_TAXONOMY_DOC,
        db_rows=[("LocalReasoner", '["reasoning", "yaml_analysis"]')],
    )
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == "capability.taxonomy.non_canonical_reference"
    assert "yaml_analysis" in f.message
    assert f.context["capability"] == "yaml_analysis"
    assert f.context["identity"] == "LocalReasoner"
    assert f.context["table"] == "core.cognitive_roles"


async def test_non_canonical_resource_capability_is_reported(tmp_path):
    ctx = _make_context(
        repo_path=tmp_path,
        taxonomy_doc=_TAXONOMY_DOC,
        db_rows=[("ollama_reasoner", '["yaml_analysis", "text_generation"]')],
    )
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "database_sources": ["core.llm_resources.provided_capabilities"],
        },
    )
    reported = {f.context["capability"] for f in findings}
    assert reported == {"yaml_analysis", "text_generation"}
    assert all(f.context["table"] == "core.llm_resources" for f in findings)
    assert all(f.context["identity"] == "ollama_reasoner" for f in findings)


async def test_invalid_artifact_reference_is_reported_with_evidence(tmp_path):
    doc_path = tmp_path / ".intent" / "workers" / "example.yaml"
    ctx = _make_context(
        repo_path=tmp_path,
        taxonomy_doc=_TAXONOMY_DOC,
        artifact_docs=[(doc_path, {"required_capabilities": ["made_up_capability"]})],
    )
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "artifact_sources": [".intent/workers/**/*"],
        },
    )
    assert len(findings) == 1
    assert findings[0].check_id == "capability.taxonomy.non_canonical_reference"
    assert findings[0].context["capability"] == "made_up_capability"
    assert findings[0].file_path == ".intent/workers/example.yaml"


async def test_unavailable_db_session_cannot_pass_vacuously(tmp_path):
    ctx = _make_context(
        repo_path=tmp_path,
        taxonomy_doc=_TAXONOMY_DOC,
        db_session=None,
    )
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
    )
    assert len(findings) == 1
    assert findings[0].check_id == "capability_taxonomy_whitelist.enforcement_failure"
    assert "ENFORCEMENT_FAILURE" in findings[0].message
    assert findings[0].context["finding_type"] == "ENFORCEMENT_FAILURE"


async def test_unreadable_taxonomy_is_enforcement_failure_not_empty_pass(tmp_path):
    ctx = _make_context(repo_path=tmp_path, taxonomy_doc=None)
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
    )
    assert len(findings) == 1
    assert findings[0].check_id == "capability_taxonomy_whitelist.enforcement_failure"
    assert findings[0].context["finding_type"] == "ENFORCEMENT_FAILURE"


async def test_taxonomy_path_cannot_escape_repo_via_absolute_path(tmp_path):
    ctx = _make_context(repo_path=tmp_path, taxonomy_doc=_TAXONOMY_DOC)
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": "/etc/passwd",
            "taxonomy_root": "families",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
    )
    assert len(findings) == 1
    assert findings[0].check_id == "capability_taxonomy_whitelist.enforcement_failure"
    assert "escapes the repository root" in findings[0].message
    ctx.intent_repo.load_document.assert_not_called()


async def test_taxonomy_path_cannot_escape_repo_via_dotdot(tmp_path):
    ctx = _make_context(repo_path=tmp_path, taxonomy_doc=_TAXONOMY_DOC)
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": "../../../../etc/passwd",
            "taxonomy_root": "families",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
    )
    assert len(findings) == 1
    assert findings[0].check_id == "capability_taxonomy_whitelist.enforcement_failure"
    assert "escapes the repository root" in findings[0].message
    ctx.intent_repo.load_document.assert_not_called()


async def test_missing_taxonomy_root_is_enforcement_failure_not_empty_pass(tmp_path):
    """A taxonomy_root naming a key absent from the document must fail
    visibly, not silently canonicalize to 'nothing is canonical, so nothing
    can violate' (a vacuous pass)."""
    ctx = _make_context(repo_path=tmp_path, taxonomy_doc=_TAXONOMY_DOC)
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "no_such_root",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
    )
    assert len(findings) == 1
    assert findings[0].check_id == "capability_taxonomy_whitelist.enforcement_failure"
    assert "zero capabilities" in findings[0].message


async def test_family_name_used_as_capability_is_rejected(tmp_path):
    """A family key (e.g. 'structured_output') is not itself a capability —
    confusing the two is exactly the live #821 drift (ConstitutionalCoherenceAnalyst
    carries 'structured_output', a family name, where a real capability like
    'structured_response' belongs)."""
    taxonomy_with_family = {
        "families": {
            "structured_output": {
                "capabilities": {
                    "json_output": {},
                    "schema_compliance": {},
                    "structured_response": {},
                }
            }
        }
    }
    ctx = _make_context(
        repo_path=tmp_path,
        taxonomy_doc=taxonomy_with_family,
        db_rows=[("SomeRole", '["structured_output"]')],
    )
    findings = await _engine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
    )
    assert len(findings) == 1
    assert findings[0].context["capability"] == "structured_output", (
        "the family key itself must not be treated as canonical — only its "
        "declared capabilities are"
    )


async def test_non_whitelisted_table_is_blocked_not_queried():
    findings = await _engine()._check_db_capability_source(
        MagicMock(db_session=AsyncMock()),
        "core.some_untrusted_table.required_capabilities",
        _CANONICAL,
    )
    assert len(findings) == 1
    assert findings[0].check_id == "knowledge_gate.table_not_whitelisted"


async def test_non_whitelisted_column_is_enforcement_failure():
    findings = await _engine()._check_db_capability_source(
        MagicMock(db_session=AsyncMock()),
        "core.cognitive_roles.some_other_column",
        _CANONICAL,
    )
    assert len(findings) == 1
    assert findings[0].check_id == "capability_taxonomy_whitelist.enforcement_failure"


def test_all_four_mappings_declare_a_now_dispatchable_check_type():
    """All four capability.taxonomy.* rules name capability_taxonomy_whitelist
    — confirm the engine now declares it, closing the #820 dispatch gap."""
    assert "capability_taxonomy_whitelist" in KnowledgeGateEngine.supported_check_types()


def test_extract_canonical_capabilities_reads_families_root():
    caps = KnowledgeGateEngine._extract_canonical_capabilities(_TAXONOMY_DOC, "families")
    assert caps == _CANONICAL


def test_extract_canonical_capabilities_empty_when_root_missing():
    assert KnowledgeGateEngine._extract_canonical_capabilities({}, "families") == set()


def test_coerce_capability_list_handles_json_string_and_list_and_none():
    assert KnowledgeGateEngine._coerce_capability_list(None) == []
    assert KnowledgeGateEngine._coerce_capability_list('["a", "b"]') == ["a", "b"]
    assert KnowledgeGateEngine._coerce_capability_list(["a", "b"]) == ["a", "b"]
    assert KnowledgeGateEngine._coerce_capability_list("not json") == []
