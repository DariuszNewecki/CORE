# tests/mind/governance/test_capability_taxonomy_disposition.py

"""#820 Group A disposition — retire the two duplicate umbrella rules.

capability.taxonomy.canonical_only and capability.taxonomy.no_ad_hoc_capabilities
dispatched through the identical (engine, check_type, database_sources,
artifact_sources) as the two precise rules and produced byte-identical
findings against live data (verified before this change). Demoted to
advisory historical markers in the rule doc; their enforcement-mapping and
remediation-map entries are removed. The two precise rules
(roles_require_canonical_capabilities, resources_provide_canonical_capabilities)
are untouched and remain the sole enforcement surface for this invariant —
this file proves that surface still produces every real finding the
umbrella rules used to duplicate, with nothing lost and nothing double-counted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import yaml

from mind.logic.engines.knowledge_gate import KnowledgeGateEngine
from shared.infrastructure.intent.rule_registry import (
    rule_requires_enforcement_mapping,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = REPO_ROOT / ".intent/rules/ai/capability_taxonomy_governance.json"
MAPPING_PATH = (
    REPO_ROOT / ".intent/enforcement/mappings/ai/capability_taxonomy_governance.yaml"
)
REMEDIATION_PATH = REPO_ROOT / ".intent/enforcement/remediation/auto_remediation.yaml"

RETIRED = {
    "capability.taxonomy.canonical_only",
    "capability.taxonomy.no_ad_hoc_capabilities",
}
PRECISE = {
    "capability.taxonomy.roles_require_canonical_capabilities",
    "capability.taxonomy.resources_provide_canonical_capabilities",
}


def _rules() -> dict[str, dict]:
    doc = json.loads(RULES_PATH.read_text())
    return {r["id"]: r for r in doc["rules"]}


def _mappings() -> dict[str, dict]:
    doc = yaml.safe_load(MAPPING_PATH.read_text())
    return doc["mappings"]


def _remediation() -> dict[str, Any]:
    doc = yaml.safe_load(REMEDIATION_PATH.read_text())
    return doc["mappings"]


def test_retired_rules_are_advisory() -> None:
    rules = _rules()
    for rule_id in RETIRED:
        assert rules[rule_id]["enforcement"] == "advisory"


def test_retired_rules_name_their_successors() -> None:
    rules = _rules()
    for rule_id in RETIRED:
        text = rules[rule_id]["statement"] + rules[rule_id].get("rationale", "")
        assert "capability.taxonomy.roles_require_canonical_capabilities" in text
        assert "capability.taxonomy.resources_provide_canonical_capabilities" in text


def test_precise_rules_remain_blocking() -> None:
    rules = _rules()
    for rule_id in PRECISE:
        assert rules[rule_id]["enforcement"] == "blocking"


def test_retired_rules_have_no_mapping() -> None:
    mappings = _mappings()
    for rule_id in RETIRED:
        assert rule_id not in mappings


def test_precise_rules_still_dispatch_through_capability_taxonomy_whitelist() -> None:
    mappings = _mappings()
    for rule_id in PRECISE:
        assert mappings[rule_id]["engine"] == "knowledge_gate"
        assert (
            mappings[rule_id]["params"]["check_type"]
            == "capability_taxonomy_whitelist"
        )


def test_retired_rules_have_no_remediation_entry() -> None:
    remediation = _remediation()
    for rule_id in RETIRED:
        assert rule_id not in remediation


def test_advisory_retired_rules_require_no_mapping() -> None:
    """Per the canonical rule_requires_enforcement_mapping predicate."""
    rules = _rules()
    for rule_id in RETIRED:
        assert rule_requires_enforcement_mapping(rules[rule_id]) is False


def test_precise_rules_still_require_a_mapping() -> None:
    rules = _rules()
    for rule_id in PRECISE:
        assert rule_requires_enforcement_mapping(rules[rule_id]) is True


def test_no_non_advisory_capability_taxonomy_rule_is_unmapped() -> None:
    """Effective coverage is unchanged: every rule in this doc that still
    requires a mapping (i.e. is not advisory) has one."""
    rules = _rules()
    mappings = _mappings()
    unmapped_non_advisory = {
        rid
        for rid, r in rules.items()
        if rule_requires_enforcement_mapping(r) and rid not in mappings
    }
    assert unmapped_non_advisory == set()


_TAXONOMY_DOC = {
    "families": {
        "reasoning": {
            "capabilities": {
                "reasoning": {},
                "analysis": {},
                "planning": {},
            }
        },
        "code": {"capabilities": {"code_generation": {}, "code_understanding": {}}},
        "structured_output": {
            "capabilities": {
                "json_output": {},
                "schema_compliance": {},
                "structured_response": {},
            }
        },
    }
}

_ROLE_ROWS = [
    (
        "ConstitutionalCoherenceAnalyst",
        '["long_context_reasoning", "structured_output"]',
    ),
    ("DocstringWriter", '["code_understanding", "documentation"]'),
    ("LocalReasoner", '["reasoning", "yaml_analysis"]'),
]
_RESOURCE_ROWS = [("ollama_reasoner", '["yaml_analysis", "text_generation"]')]


async def test_live_diagnostic_yields_exactly_six_findings_no_duplication(
    tmp_path: Path,
) -> None:
    """The two precise DB-backed rules together produce exactly 4 role + 2
    resource findings — the same six real findings the umbrella rules used
    to duplicate, with no double-counting now that canonical_only and
    no_ad_hoc_capabilities no longer dispatch at all."""
    mappings = _mappings()
    engine = KnowledgeGateEngine()

    all_findings = []
    for rule_id, rows in (
        ("capability.taxonomy.roles_require_canonical_capabilities", _ROLE_ROWS),
        (
            "capability.taxonomy.resources_provide_canonical_capabilities",
            _RESOURCE_ROWS,
        ),
    ):
        ctx = MagicMock()
        ctx.repo_path = tmp_path
        ctx.intent_repo.load_document = MagicMock(return_value=_TAXONOMY_DOC)
        session = AsyncMock()
        result = MagicMock()
        result.fetchall = MagicMock(return_value=rows)
        session.execute = AsyncMock(return_value=result)
        ctx.db_session = session

        findings = await engine._check_capability_taxonomy_whitelist(
            ctx, mappings[rule_id]["params"]
        )
        all_findings.extend(findings)

    assert len(all_findings) == 6
    role_findings = [
        f for f in all_findings if f.context["table"] == "core.cognitive_roles"
    ]
    resource_findings = [
        f for f in all_findings if f.context["table"] == "core.llm_resources"
    ]
    assert len(role_findings) == 4
    assert len(resource_findings) == 2
