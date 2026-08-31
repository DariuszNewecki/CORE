# tests/mind/logic/engines/test_knowledge_gate__resources_provide_canonical_capabilities.py

"""#842 Unit J: the compliant half of capability.taxonomy.resources_provide_canonical_capabilities.

test_knowledge_gate__capability_taxonomy_whitelist.py already covers
this rule's violating fixture
(test_non_canonical_resource_capability_is_reported, against the
rule's live core.llm_resources.provided_capabilities database_source)
and the shared dependency-absence / enforcement-failure behavior for
the check_type as a whole. It does not carry a compliant fixture keyed
to core.llm_resources specifically (its one compliant fixture uses
core.cognitive_roles, backing the sibling
roles_require_canonical_capabilities rule instead) -- this file closes
that gap with a precise same-source compliant pair.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from mind.logic.engines.knowledge_gate import KnowledgeGateEngine


_TAXONOMY_DOC = {
    "families": {
        "reasoning": {"capabilities": {"reasoning": {}, "analysis": {}}},
        "code": {"capabilities": {"code_generation": {}}},
    }
}


def _make_context(
    *, repo_path: Path, db_rows: list[tuple[Any, Any]]
) -> MagicMock:
    ctx = MagicMock()
    ctx.repo_path = repo_path
    intent_repo = MagicMock()
    intent_repo.load_document = MagicMock(return_value=_TAXONOMY_DOC)
    ctx.intent_repo = intent_repo

    session = MagicMock()
    result = MagicMock()
    result.fetchall = MagicMock(return_value=db_rows)

    async def _execute(*_args: Any, **_kwargs: Any) -> Any:
        return result

    session.execute = _execute
    ctx.db_session = session
    return ctx


async def test_canonical_llm_resources_capabilities_pass_with_no_findings(
    tmp_path: Path,
) -> None:
    """core.llm_resources.provided_capabilities rows whose values are all
    canonical produce zero findings -- the resources_provide_canonical_
    capabilities rule's own database_source, matching its live mapping."""
    ctx = _make_context(
        repo_path=tmp_path,
        db_rows=[("ollama_reasoner", '["reasoning", "code_generation"]')],
    )
    findings = await KnowledgeGateEngine()._check_capability_taxonomy_whitelist(
        ctx,
        {
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "database_sources": ["core.llm_resources.provided_capabilities"],
        },
    )
    assert findings == []
