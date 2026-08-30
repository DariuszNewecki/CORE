# tests/mind/governance/test_g2_blocking_rule_registry.py

"""G2 blocking-rule census ratchet (#842 Unit A).

The registry at ``.specs/verification/g2_blocking_rule_registry.yaml`` is the
source-derived instrument for URS-production-readiness.md's G2 requirement:
one row per blocking rule, carrying its mapped engine, mechanism class, and
(once depth-verified) violating/compliant fixture references.

This test is the ratchet, not the proof. It does not assert G2 is satisfied
-- most rows are still ``state: "unverified"`` with null fixture refs by
design (subsequent #842 units do the depth-verification and fixture
authoring). What it guarantees on every CI run:

  1. The registry's rule_id set is in exact agreement with the live
     blocking-rule set derived from .intent/rules/**/*.json -- no missing
     rows, no extra rows, no duplicates. A newly added blocking rule with
     no registry row fails this test, by construction of the set-equality
     check.
  2. Each row's recorded ``engine`` and ``mechanism_class`` agree with the
     live .intent/enforcement/mappings/**/*.yaml corpus (via the same
     EnforcementMappingLoader production code uses), so a mapping change
     that isn't mirrored into the registry is caught.
  3. ``state`` is drawn from the closed vocabulary the registry's own
     header documents.
  4. A ``state: "verified"`` row cannot silently lose either fixture
     reference -- both must be non-null and must resolve to a real test
     file containing that function name.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from mind.governance.enforcement_loader import EnforcementMappingLoader
from shared.infrastructure.intent.rule_registry import get_rule_enforcement_map


_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_REGISTRY_PATH = _REPO_ROOT / ".specs" / "verification" / "g2_blocking_rule_registry.yaml"

_CONVENTIONAL_ENGINES = {
    "ast_gate",
    "regex_gate",
    "artifact_gate",
    "python_runtime",
    "glob_gate",
    "cli_gate",
    "taxonomy_gate",
    "workflow_gate",
    "knowledge_gate",
    "contracts_gate",
    "runtime_gate",
}

_VALID_STATES = {"unverified", "gap", "decision_required", "verified"}


def _load_registry() -> list[dict[str, Any]]:
    data = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return data["entries"]


def _live_blocking_rule_ids() -> set[str]:
    enforcement_map = get_rule_enforcement_map()
    return {rid for rid, tier in enforcement_map.items() if tier == "blocking"}


def _live_mechanism_class(engine: str | None, params: dict[str, Any]) -> str:
    if engine in _CONVENTIONAL_ENGINES:
        return "engine_mapped"
    if engine == "passive_gate":
        attestation_class = str(params.get("attestation_class", "")).lower()
        if attestation_class:
            return f"passive_gate_class_{attestation_class}"
        return "passive_gate_unclassified"
    if engine == "advisory":
        return "advisory_mapped"
    return f"other:{engine}"


# ID: d8e0cf2b-0661-4db7-aa9a-27a28321def9
def test_registry_rule_id_set_matches_live_blocking_rules() -> None:
    """No missing, extra, or duplicate rows -- exact agreement with source."""
    entries = _load_registry()
    registry_ids = [e["rule_id"] for e in entries]

    assert len(registry_ids) == len(set(registry_ids)), (
        "Duplicate rule_id rows in g2_blocking_rule_registry.yaml: "
        f"{[rid for rid in registry_ids if registry_ids.count(rid) > 1]}"
    )

    registry_id_set = set(registry_ids)
    live_id_set = _live_blocking_rule_ids()

    missing = live_id_set - registry_id_set
    extra = registry_id_set - live_id_set

    assert not missing, (
        f"Blocking rule(s) with no registry row (add before merging): {sorted(missing)}"
    )
    assert not extra, (
        f"Registry row(s) for rule(s) no longer blocking (or removed): {sorted(extra)}"
    )


# ID: ffa32307-5b83-4d01-ad8b-5ee69b1e53c8
def test_registry_engine_and_mechanism_class_agree_with_live_mappings() -> None:
    """A mapping change not mirrored into the registry fails here."""
    loader = EnforcementMappingLoader(_REPO_ROOT / ".intent")
    mappings = loader.load_all_mappings()

    for entry in _load_registry():
        rule_id = entry["rule_id"]
        strategy = mappings.get(rule_id)
        assert strategy is not None, f"{rule_id}: no live enforcement mapping found"

        live_engine = strategy.get("engine")
        assert entry["engine"] == live_engine, (
            f"{rule_id}: registry engine {entry['engine']!r} != "
            f"live mapping engine {live_engine!r}"
        )

        live_mech = _live_mechanism_class(live_engine, strategy.get("params") or {})
        assert entry["mechanism_class"] == live_mech, (
            f"{rule_id}: registry mechanism_class {entry['mechanism_class']!r} != "
            f"live-derived {live_mech!r}"
        )


# ID: 31bc0504-f4cd-4ece-b6e7-8a8a29338f6c
def test_registry_states_are_from_closed_vocabulary() -> None:
    for entry in _load_registry():
        assert entry["state"] in _VALID_STATES, (
            f"{entry['rule_id']}: state {entry['state']!r} not in {_VALID_STATES}"
        )


def _resolve_fixture_ref(ref: str) -> None:
    """Raise AssertionError unless ref is 'path/to/test_file.py::function_name'
    where the file exists under the repo and defines that function."""
    assert "::" in ref, f"Fixture reference {ref!r} is not 'path::function' shaped"
    rel_path, func_name = ref.split("::", 1)
    file_path = _REPO_ROOT / rel_path
    assert file_path.is_file(), f"Fixture reference {ref!r}: {rel_path} does not exist"

    source = file_path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^(async )?def {re.escape(func_name)}\(", re.MULTILINE)
    assert pattern.search(source), (
        f"Fixture reference {ref!r}: no def {func_name}(...) found in {rel_path}"
    )


# ID: 49d1279f-517d-4490-aed8-1d8e129c47bd
def test_verified_rows_carry_both_real_fixture_references() -> None:
    """The ratchet: a 'verified' row cannot silently lose either fixture ref."""
    verified = [e for e in _load_registry() if e["state"] == "verified"]
    assert verified, (
        "Expected at least one verified row (atomic_actions.fix_action_scope) "
        "-- if this legitimately dropped to zero, something regressed"
    )

    for entry in verified:
        rule_id = entry["rule_id"]
        violating = entry.get("violating_fixture")
        compliant = entry.get("compliant_fixture")
        assert violating, f"{rule_id}: state=verified but violating_fixture is null"
        assert compliant, f"{rule_id}: state=verified but compliant_fixture is null"
        _resolve_fixture_ref(violating)
        _resolve_fixture_ref(compliant)


# ID: f7a8d354-07cc-4da1-a7bb-2cfd4dcf9bb3
def test_non_verified_rows_have_no_dangling_fixture_references() -> None:
    """A row that isn't verified but names a fixture must still resolve --
    catches a half-filled-in row (fixture written, state left stale)."""
    for entry in _load_registry():
        if entry["state"] == "verified":
            continue
        for key in ("violating_fixture", "compliant_fixture"):
            ref = entry.get(key)
            if ref is not None:
                _resolve_fixture_ref(ref)
