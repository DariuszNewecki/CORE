# tests/shared/infrastructure/intent/test_rule_registry.py
"""Tests for shared.infrastructure.intent.rule_registry."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure lru_cache does not leak state between tests."""
    from shared.infrastructure.intent.rule_registry import (
        get_rule_enforcement_map,
        get_rule_registry,
    )

    get_rule_registry.cache_clear()
    get_rule_enforcement_map.cache_clear()
    yield
    get_rule_registry.cache_clear()
    get_rule_enforcement_map.cache_clear()


def test_returns_non_empty_dict():
    from shared.infrastructure.intent.rule_registry import get_rule_registry

    registry = get_rule_registry()
    assert isinstance(registry, dict)
    assert len(registry) > 0, "RuleRegistry must load at least one rule ID"


def test_known_stable_rule_ids_present():
    from shared.infrastructure.intent.rule_registry import get_rule_registry

    registry = get_rule_registry()
    stable = [
        "ai.prompt.model_required",
        "governance.remediation.all_rules_mapped",
        "linkage.assign_ids",
        "architecture.boundary.settings_access",
    ]
    for rule_id in stable:
        assert rule_id in registry, f"Expected stable rule ID missing: {rule_id}"


def test_rule_id_maps_to_itself():
    from shared.infrastructure.intent.rule_registry import get_rule_registry

    registry = get_rule_registry()
    rule_id = "ai.prompt.model_required"
    assert registry[rule_id] == rule_id


def test_unknown_id_raises_key_error():
    from shared.infrastructure.intent.rule_registry import get_rule_registry

    registry = get_rule_registry()
    with pytest.raises(KeyError):
        _ = registry["this.rule.does.not.exist.at.all"]


def test_result_is_cached():
    from shared.infrastructure.intent.rule_registry import get_rule_registry

    r1 = get_rule_registry()
    r2 = get_rule_registry()
    assert r1 is r2, "get_rule_registry() must return the same object on repeated calls"


# ---------------------------------------------------------------------------
# rule_requires_enforcement_mapping — the canonical mapping-required predicate
# (#820 Group B prerequisite). One definition, shared by DispatchParityCheck
# and the audit unmapped-rule statistics.
# ---------------------------------------------------------------------------


def test_blocking_rule_requires_mapping():
    from shared.infrastructure.intent.rule_registry import (
        rule_requires_enforcement_mapping,
    )

    assert rule_requires_enforcement_mapping({"enforcement": "blocking"}) is True


def test_reporting_rule_requires_mapping():
    from shared.infrastructure.intent.rule_registry import (
        rule_requires_enforcement_mapping,
    )

    assert rule_requires_enforcement_mapping({"enforcement": "reporting"}) is True


def test_advisory_rule_does_not_require_mapping():
    from shared.infrastructure.intent.rule_registry import (
        rule_requires_enforcement_mapping,
    )

    assert rule_requires_enforcement_mapping({"enforcement": "advisory"}) is False


def test_missing_enforcement_fails_closed_toward_visibility():
    """A rule with no enforcement tier is treated as requiring a mapping.

    Fail-closed: a malformed rule surfaces as an unmapped-rule finding rather
    than silently escaping coverage by being mistaken for advisory.
    """
    from shared.infrastructure.intent.rule_registry import (
        rule_requires_enforcement_mapping,
    )

    assert rule_requires_enforcement_mapping({}) is True
    assert rule_requires_enforcement_mapping({"enforcement": None}) is True
    assert rule_requires_enforcement_mapping({"enforcement": "typo"}) is True


# ---------------------------------------------------------------------------
# get_rule_enforcement_map — companion index, id -> declared enforcement tier
# ---------------------------------------------------------------------------


def test_enforcement_map_returns_non_empty_dict():
    from shared.infrastructure.intent.rule_registry import get_rule_enforcement_map

    enforcement_map = get_rule_enforcement_map()
    assert isinstance(enforcement_map, dict)
    assert len(enforcement_map) > 0, "Enforcement map must load at least one rule ID"


def test_enforcement_map_same_id_set_as_registry():
    from shared.infrastructure.intent.rule_registry import (
        get_rule_enforcement_map,
        get_rule_registry,
    )

    assert set(get_rule_enforcement_map()) == set(get_rule_registry()), (
        "Both indexes scan the same .intent/rules/**/*.json corpus and must "
        "agree on which rule IDs exist"
    )


def test_enforcement_map_known_stable_tiers():
    from shared.infrastructure.intent.rule_registry import get_rule_enforcement_map

    enforcement_map = get_rule_enforcement_map()
    assert enforcement_map["architecture.boundary.settings_access"] == "blocking"


def test_enforcement_map_is_cached():
    from shared.infrastructure.intent.rule_registry import get_rule_enforcement_map

    m1 = get_rule_enforcement_map()
    m2 = get_rule_enforcement_map()
    assert m1 is m2, (
        "get_rule_enforcement_map() must return the same object on repeated calls"
    )
