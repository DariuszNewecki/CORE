# tests/mind/governance/test_component_responsibility_disposition.py

"""#820 Group B disposition — reconcile the six inert component_responsibility rules.

All six shared the same dispatch shape as capability.taxonomy.* before
Group A: engine=knowledge_gate, check_type=component_responsibility, a
check_type no engine ever implemented, so each dispatched to nothing and
reported clean on every audit.

Three are retired as advisory historical markers, each naming the concrete
mechanical rule(s) that already cover its real surface:
  - architecture.layers.no_mind_execution      -> the four architecture.mind.* rules
  - architecture.will.must_delegate_to_body    -> will.no_direct_database_access,
                                                   will.no_filesystem_operations
  - architecture.api.must_route_through_will   -> api.no_direct_database_access,
                                                   api.no_body_bypass

Three are preserved as advisory doctrine (no mechanical replacement exists
or is invented — "strategic decision" and "business logic" are semantic
judgments, not patterns any engine verifies):
  - architecture.shared.no_strategic_decisions
  - infrastructure.no_business_logic
  - infrastructure.no_strategic_decisions

All six: enforcement -> advisory, mapping removed, remediation entry removed.
No engine change, no new check_type, no #821/Group C work.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from mind.governance.enforcement_loader import EnforcementMappingLoader
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.intent.rule_registry import (
    rule_requires_enforcement_mapping,
)


REPO_ROOT = Path(__file__).resolve().parents[3]

LAYER_RULES_PATH = REPO_ROOT / ".intent/rules/architecture/layer_separation.json"
INFRA_RULES_PATH = REPO_ROOT / ".intent/rules/infrastructure/authority_boundaries.json"
LAYER_MAPPING_PATH = (
    REPO_ROOT / ".intent/enforcement/mappings/architecture/layer_separation.yaml"
)
INFRA_MAPPING_PATH = (
    REPO_ROOT / ".intent/enforcement/mappings/infrastructure/authority_boundaries.yaml"
)
REMEDIATION_PATH = REPO_ROOT / ".intent/enforcement/remediation/auto_remediation.yaml"

MBW_PAPER_PATH = REPO_ROOT / ".specs/papers/CORE-Mind-Body-Will-Separation.md"
INFRA_PAPER_PATH = REPO_ROOT / ".specs/papers/CORE-Infrastructure-Definition.md"

RETIRED_WITH_SUCCESSORS = {
    "architecture.layers.no_mind_execution": {
        "architecture.mind.no_database_access",
        "architecture.mind.no_filesystem_writes",
        "architecture.mind.no_body_invocation",
        "architecture.mind.no_will_invocation",
    },
    "architecture.will.must_delegate_to_body": {
        "architecture.will.no_direct_database_access",
        "architecture.will.no_filesystem_operations",
    },
    "architecture.api.must_route_through_will": {
        "architecture.api.no_direct_database_access",
        "architecture.api.no_body_bypass",
    },
}
DOCTRINE_PRESERVED = {
    "architecture.shared.no_strategic_decisions",
    "infrastructure.no_business_logic",
    "infrastructure.no_strategic_decisions",
}
ALL_SIX = set(RETIRED_WITH_SUCCESSORS) | DOCTRINE_PRESERVED

# The concrete mechanical rules named above must remain unchanged: still
# mapped, still their original enforcement tier.
UNCHANGED_SIBLINGS = {
    "architecture.mind.no_database_access": "reporting",
    "architecture.mind.no_filesystem_writes": "reporting",
    "architecture.mind.no_body_invocation": "reporting",
    "architecture.mind.no_will_invocation": "reporting",
    "architecture.will.no_direct_database_access": "reporting",
    "architecture.will.no_filesystem_operations": "reporting",
    "architecture.api.no_direct_database_access": "reporting",
    "architecture.api.no_body_bypass": "reporting",
    "architecture.shared.no_layer_imports": "blocking",
}


def _all_rules() -> dict[str, dict]:
    rules: dict[str, dict] = {}
    for path in (LAYER_RULES_PATH, INFRA_RULES_PATH):
        doc = json.loads(path.read_text())
        rules.update({r["id"]: r for r in doc["rules"]})
    return rules


def _all_mappings() -> dict[str, dict]:
    mappings: dict[str, dict] = {}
    for path in (LAYER_MAPPING_PATH, INFRA_MAPPING_PATH):
        doc = yaml.safe_load(path.read_text())
        mappings.update(doc["mappings"])
    return mappings


def _remediation() -> dict[str, Any]:
    doc = yaml.safe_load(REMEDIATION_PATH.read_text())
    return doc["mappings"]


def test_all_six_rules_are_advisory() -> None:
    rules = _all_rules()
    for rule_id in ALL_SIX:
        assert rules[rule_id]["enforcement"] == "advisory", rule_id


def test_all_six_mappings_are_removed() -> None:
    mappings = _all_mappings()
    for rule_id in ALL_SIX:
        assert rule_id not in mappings, rule_id


def test_all_six_remediation_entries_are_removed() -> None:
    remediation = _remediation()
    for rule_id in ALL_SIX:
        assert rule_id not in remediation, rule_id


def test_none_of_the_six_are_reported_as_unmapped() -> None:
    """Per the canonical rule_requires_enforcement_mapping predicate, an
    advisory rule requires no mapping — none of the six should surface as
    an unmapped-rule finding."""
    rules = _all_rules()
    for rule_id in ALL_SIX:
        assert rule_requires_enforcement_mapping(rules[rule_id]) is False, rule_id


def test_zero_non_advisory_rules_unmapped_repo_wide() -> None:
    """Effective coverage excludes the six advisory rules correctly across
    the WHOLE repo (not just these two rule docs): every rule that still
    requires a mapping, anywhere in .intent/rules/, has one, via the real
    IntentRepository/EnforcementMappingLoader loading path."""
    repo = get_intent_repository()
    repo.initialize()
    all_mappings = EnforcementMappingLoader(repo.root).load_all_mappings()

    unmapped_non_advisory = []
    for rule_id in repo.known_rule_ids():
        ref = repo.get_rule(rule_id)
        if rule_requires_enforcement_mapping(ref.content) and rule_id not in all_mappings:
            unmapped_non_advisory.append(rule_id)

    assert unmapped_non_advisory == []
    for rule_id in ALL_SIX:
        assert rule_id not in all_mappings


def test_retired_rules_name_their_successors() -> None:
    rules = _all_rules()
    for rule_id, successors in RETIRED_WITH_SUCCESSORS.items():
        text = rules[rule_id]["statement"] + rules[rule_id].get("rationale", "")
        assert "RETIRED" in rules[rule_id]["statement"], rule_id
        for successor in successors:
            assert successor in text, f"{rule_id} does not name {successor}"


def test_doctrine_rules_remain_normative_not_retired() -> None:
    rules = _all_rules()
    for rule_id in DOCTRINE_PRESERVED:
        statement = rules[rule_id]["statement"]
        assert "RETIRED" not in statement, rule_id
        assert "superseded" not in statement.lower(), rule_id
        # Still states the original normative principle in some recognizable form.
        assert "MUST" in statement, rule_id


def test_doctrine_rules_require_human_review() -> None:
    rules = _all_rules()
    for rule_id in DOCTRINE_PRESERVED:
        text = rules[rule_id]["statement"] + rules[rule_id].get("rationale", "")
        assert "governor" in text.lower() or "human" in text.lower(), rule_id


def test_unchanged_mechanical_siblings_are_untouched() -> None:
    rules = _all_rules()
    mappings = _all_mappings()
    for rule_id, expected_enforcement in UNCHANGED_SIBLINGS.items():
        assert rules[rule_id]["enforcement"] == expected_enforcement, rule_id
        assert rule_id in mappings, f"{rule_id} must remain mapped"


def test_mbw_paper_no_longer_claims_blocking_ast_upgrade() -> None:
    text = MBW_PAPER_PATH.read_text()
    assert "is upgraded from advisory" not in text
    assert "architecture.shared.no_layer_imports" in text
    assert "not mechanically decidable" in text


def test_infrastructure_paper_no_longer_claims_blocking_mapping() -> None:
    text = INFRA_PAPER_PATH.read_text()
    # The fabricated mapping-YAML block (claiming a real `enforcement:
    # blocking` mapping) is gone entirely — no yaml fence remains in the
    # paper at all. A mention of "enforcement: blocking" in corrective prose
    # describing the historical false claim is expected and fine; a live
    # yaml code fence asserting it is not.
    assert "```yaml" not in text
    assert "No enforcement mapping exists" in text


def test_infrastructure_paper_6_1_and_6_2_no_longer_contradict() -> None:
    text = INFRA_PAPER_PATH.read_text()
    # 6.1 must no longer list the strategic-decision prohibition as
    # something infrastructure is exempt FROM.
    section_6_1_start = text.index("### 6.1 Constitutional Exemption")
    section_6_2_start = text.index("### 6.2 Claiming Infrastructure Status")
    section_6_1 = text[section_6_1_start:section_6_2_start]
    assert "Strategic decision prohibition (no decisions to make)" not in section_6_1
    assert "not** exempt from the no-strategic-decisions" in section_6_1
