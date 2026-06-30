# tests/shared/infrastructure/intent/test_operational_capabilities.py
"""
Loader tests for ``shared.infrastructure.intent.operational_capabilities``.

One test per ADR-078 D10 rejection clause, plus happy-path coverage of the
hashable tuple-of-pairs representation and the as_mapping property. The
loader is the validation chokepoint for `.intent/taxonomies/operational_capabilities.yaml`;
these tests pin its fail-closed contract.

Tests construct a synthetic minimal-valid `.intent/` tree under tmp_path
and mutate one file per case to trigger a specific rejection. The happy
path also exercises the live repo's tree by calling the loader with no
repo_root argument (default to the actual repo root).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.infrastructure.intent.operational_capabilities import (
    FsPatternEntry,
    OperationalCapabilityTaxonomyError,
    load_operational_capabilities,
)


_MINIMAL_ENUMS: dict = {
    "definitions": {
        "fs_operation_class": {"enum": ["read", "create", "modify", "delete"]},
        "operational_mode": {"enum": ["dev", "live"]},
    }
}

_MINIMAL_ACTION_RISK = "actions:\n  fix.example: safe\n"

_MINIMAL_TAXONOMY = (
    "capabilities:\n"
    "  fix.example:\n"
    "    description: A minimal valid capability\n"
    "    risk: safe\n"
    "    fs_profile:\n"
    "      read: []\n"
    "      create: []\n"
    "      modify: []\n"
    "      delete: []\n"
)


@pytest.fixture
def intent_tree(tmp_path: Path) -> Callable[..., Path]:
    """
    Build a minimal valid .intent/ tree under tmp_path. Returns a callable
    that accepts optional override kwargs (enums_json, action_risk_yaml,
    taxonomy_yaml) to mutate one or more files before returning the
    repo_root.
    """

    def _factory(
        *,
        enums_json: str | None = None,
        action_risk_yaml: str | None = None,
        taxonomy_yaml: str | None = None,
        skip_enums: bool = False,
        skip_action_risk: bool = False,
        skip_taxonomy: bool = False,
    ) -> Path:
        (tmp_path / ".intent/META").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".intent/enforcement/config").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".intent/taxonomies").mkdir(parents=True, exist_ok=True)

        if not skip_enums:
            (tmp_path / ".intent/META/enums.json").write_text(
                enums_json if enums_json is not None else json.dumps(_MINIMAL_ENUMS)
            )
        if not skip_action_risk:
            (tmp_path / ".intent/enforcement/config/action_risk.yaml").write_text(
                action_risk_yaml
                if action_risk_yaml is not None
                else _MINIMAL_ACTION_RISK
            )
        if not skip_taxonomy:
            (tmp_path / ".intent/taxonomies/operational_capabilities.yaml").write_text(
                taxonomy_yaml if taxonomy_yaml is not None else _MINIMAL_TAXONOMY
            )
        return tmp_path

    return _factory


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_minimal_tree_loads(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree()
    caps = load_operational_capabilities(repo_root=root)
    assert isinstance(caps, frozenset)
    assert len(caps) == 1
    cap = next(iter(caps))
    assert cap.id == "fix.example"
    assert cap.risk == "safe"
    assert cap.description == "A minimal valid capability"


def test_happy_path_live_repo_loads() -> None:
    """The actual repo's .intent/ tree must load cleanly — implementation gate."""
    caps = load_operational_capabilities()
    assert isinstance(caps, frozenset)
    assert len(caps) >= 1
    ids = {c.id for c in caps}
    assert "fix.format" in ids


def test_capability_is_hashable_for_frozenset(intent_tree: Callable[..., Path]) -> None:
    """Hashability is required for frozenset membership — Patch A invariant."""
    root = intent_tree()
    caps = load_operational_capabilities(repo_root=root)
    # If OperationalCapability is unhashable, frozenset() above would have
    # raised TypeError. Explicitly hash one entry to make the contract loud.
    hash(next(iter(caps)))


def test_as_mapping_property_returns_view(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree()
    caps = load_operational_capabilities(repo_root=root)
    cap = next(iter(caps))
    mapping = cap.as_mapping
    assert set(mapping.keys()) == {"read", "create", "modify", "delete"}
    assert mapping["read"] == ()


def test_fs_profile_pair_order_matches_enum(intent_tree: Callable[..., Path]) -> None:
    """Tuple-of-pairs order is canonical, sourced from fs_operation_class.enum."""
    root = intent_tree()
    caps = load_operational_capabilities(repo_root=root)
    cap = next(iter(caps))
    order = [op_class for op_class, _ in cap.fs_profile]
    assert order == ["read", "create", "modify", "delete"]


def test_pattern_entries_have_tuple_modes(intent_tree: Callable[..., Path]) -> None:
    """Modes are stored as tuples (not lists) so FsPatternEntry is hashable."""
    taxonomy = (
        "capabilities:\n"
        "  fix.example:\n"
        "    description: With one pattern entry\n"
        "    risk: safe\n"
        "    fs_profile:\n"
        "      read:\n"
        "        - {path_pattern: 'src/**/*.py', modes: [dev, live]}\n"
        "      create: []\n"
        "      modify: []\n"
        "      delete: []\n"
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    caps = load_operational_capabilities(repo_root=root)
    cap = next(iter(caps))
    entries = cap.as_mapping["read"]
    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, FsPatternEntry)
    assert entry.path_pattern == "src/**/*.py"
    assert entry.modes == ("dev", "live")
    hash(entry)


# ---------------------------------------------------------------------------
# D10 rejection clauses — one test per failure mode
# ---------------------------------------------------------------------------


def test_missing_taxonomy_file_raises(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree(skip_taxonomy=True)
    with patch(
        "shared.infrastructure.intent.operational_capabilities.resolve_floor_path",
        return_value=None,
    ):
        with pytest.raises(OperationalCapabilityTaxonomyError, match="taxonomy missing"):
            load_operational_capabilities(repo_root=root)


def test_malformed_yaml_raises(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree(taxonomy_yaml="capabilities:\n  fix.example:\n    : [")
    with pytest.raises(OperationalCapabilityTaxonomyError, match="malformed YAML"):
        load_operational_capabilities(repo_root=root)


def test_top_level_not_mapping_raises(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree(taxonomy_yaml="- not\n- a\n- mapping\n")
    with pytest.raises(
        OperationalCapabilityTaxonomyError, match="top-level document must be a mapping"
    ):
        load_operational_capabilities(repo_root=root)


def test_missing_capabilities_block_raises(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree(taxonomy_yaml="other_key: value\n")
    with pytest.raises(
        OperationalCapabilityTaxonomyError,
        match="missing or non-mapping 'capabilities:' block",
    ):
        load_operational_capabilities(repo_root=root)


def test_empty_capabilities_block_raises(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree(taxonomy_yaml="capabilities: {}\n")
    with pytest.raises(
        OperationalCapabilityTaxonomyError, match="declares no capabilities"
    ):
        load_operational_capabilities(repo_root=root)


def test_d6_grammar_violation_hyphen_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = _MINIMAL_TAXONOMY.replace("fix.example", "fix.has-hyphen")
    risk = "actions:\n  fix.has-hyphen: safe\n"
    root = intent_tree(taxonomy_yaml=taxonomy, action_risk_yaml=risk)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="violates D6 grammar"):
        load_operational_capabilities(repo_root=root)


def test_d6_grammar_violation_nested_dot_raises(
    intent_tree: Callable[..., Path],
) -> None:
    taxonomy = _MINIMAL_TAXONOMY.replace("fix.example", "sync.has.nested")
    risk = "actions:\n  sync.has.nested: safe\n"
    root = intent_tree(taxonomy_yaml=taxonomy, action_risk_yaml=risk)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="violates D6 grammar"):
        load_operational_capabilities(repo_root=root)


def test_d8_chokepoint_primitive_id_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = _MINIMAL_TAXONOMY.replace("fix.example", "file.create")
    risk = "actions:\n  file.create: safe\n"
    root = intent_tree(taxonomy_yaml=taxonomy, action_risk_yaml=risk)
    with pytest.raises(
        OperationalCapabilityTaxonomyError, match="chokepoint primitive"
    ):
        load_operational_capabilities(repo_root=root)


def test_missing_description_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = (
        "capabilities:\n"
        "  fix.example:\n"
        "    risk: safe\n"
        "    fs_profile:\n"
        "      read: []\n"
        "      create: []\n"
        "      modify: []\n"
        "      delete: []\n"
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    with pytest.raises(
        OperationalCapabilityTaxonomyError, match="missing required field"
    ):
        load_operational_capabilities(repo_root=root)


def test_unknown_capability_field_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = _MINIMAL_TAXONOMY.replace(
        "    risk: safe\n",
        "    risk: safe\n    extra_field: not_allowed\n",
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="unknown field"):
        load_operational_capabilities(repo_root=root)


def test_risk_outside_vocabulary_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = _MINIMAL_TAXONOMY.replace("risk: safe", "risk: catastrophic")
    risk = "actions:\n  fix.example: catastrophic\n"
    root = intent_tree(taxonomy_yaml=taxonomy, action_risk_yaml=risk)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="is not in"):
        load_operational_capabilities(repo_root=root)


def test_risk_not_in_action_risk_raises(intent_tree: Callable[..., Path]) -> None:
    risk = "actions:\n  some.other_action: safe\n"
    root = intent_tree(action_risk_yaml=risk)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="not declared in"):
        load_operational_capabilities(repo_root=root)


def test_risk_value_disagreement_raises(intent_tree: Callable[..., Path]) -> None:
    risk = "actions:\n  fix.example: dangerous\n"
    root = intent_tree(action_risk_yaml=risk)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="disagrees with"):
        load_operational_capabilities(repo_root=root)


def test_fs_profile_missing_key_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = (
        "capabilities:\n"
        "  fix.example:\n"
        "    description: Missing delete key\n"
        "    risk: safe\n"
        "    fs_profile:\n"
        "      read: []\n"
        "      create: []\n"
        "      modify: []\n"
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    with pytest.raises(
        OperationalCapabilityTaxonomyError, match="missing required op-class key"
    ):
        load_operational_capabilities(repo_root=root)


def test_fs_profile_unknown_key_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = _MINIMAL_TAXONOMY.replace(
        "      delete: []\n",
        "      delete: []\n      unknown_op: []\n",
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="unknown key"):
        load_operational_capabilities(repo_root=root)


def test_pattern_entry_empty_modes_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = (
        "capabilities:\n"
        "  fix.example:\n"
        "    description: Empty modes\n"
        "    risk: safe\n"
        "    fs_profile:\n"
        "      read:\n"
        "        - {path_pattern: 'src/**/*.py', modes: []}\n"
        "      create: []\n"
        "      modify: []\n"
        "      delete: []\n"
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="'modes' is empty"):
        load_operational_capabilities(repo_root=root)


def test_pattern_entry_unknown_mode_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = (
        "capabilities:\n"
        "  fix.example:\n"
        "    description: Unknown mode\n"
        "    risk: safe\n"
        "    fs_profile:\n"
        "      read:\n"
        "        - {path_pattern: 'src/**/*.py', modes: [debug]}\n"
        "      create: []\n"
        "      modify: []\n"
        "      delete: []\n"
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    with pytest.raises(
        OperationalCapabilityTaxonomyError, match="outside operational_mode"
    ):
        load_operational_capabilities(repo_root=root)


def test_pattern_entry_missing_path_pattern_raises(
    intent_tree: Callable[..., Path],
) -> None:
    taxonomy = (
        "capabilities:\n"
        "  fix.example:\n"
        "    description: Missing path_pattern\n"
        "    risk: safe\n"
        "    fs_profile:\n"
        "      read:\n"
        "        - {modes: [dev]}\n"
        "      create: []\n"
        "      modify: []\n"
        "      delete: []\n"
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    with pytest.raises(OperationalCapabilityTaxonomyError, match="entry missing field"):
        load_operational_capabilities(repo_root=root)


def test_pattern_entry_unknown_field_raises(intent_tree: Callable[..., Path]) -> None:
    taxonomy = (
        "capabilities:\n"
        "  fix.example:\n"
        "    description: Pattern entry has extra field\n"
        "    risk: safe\n"
        "    fs_profile:\n"
        "      read:\n"
        "        - {path_pattern: 'src/**/*.py', modes: [dev], extra: bad}\n"
        "      create: []\n"
        "      modify: []\n"
        "      delete: []\n"
    )
    root = intent_tree(taxonomy_yaml=taxonomy)
    with pytest.raises(
        OperationalCapabilityTaxonomyError, match="entry has unknown field"
    ):
        load_operational_capabilities(repo_root=root)


# ---------------------------------------------------------------------------
# enums.json + action_risk.yaml load failure modes
# ---------------------------------------------------------------------------


def test_missing_enums_file_raises(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree(skip_enums=True)
    with patch(
        "shared.infrastructure.intent.operational_capabilities.resolve_floor_path",
        return_value=None,
    ):
        with pytest.raises(
            OperationalCapabilityTaxonomyError, match="required enum file missing"
        ):
            load_operational_capabilities(repo_root=root)


def test_missing_action_risk_file_raises(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree(skip_action_risk=True)
    with patch(
        "shared.infrastructure.intent.operational_capabilities.resolve_floor_path",
        return_value=None,
    ):
        with pytest.raises(
            OperationalCapabilityTaxonomyError, match="required risk file missing"
        ):
            load_operational_capabilities(repo_root=root)


def test_malformed_enums_json_raises(intent_tree: Callable[..., Path]) -> None:
    root = intent_tree(enums_json="{not valid json")
    with pytest.raises(OperationalCapabilityTaxonomyError, match="malformed JSON"):
        load_operational_capabilities(repo_root=root)


def test_missing_fs_operation_class_enum_raises(
    intent_tree: Callable[..., Path],
) -> None:
    bad_enums = json.dumps(
        {
            "definitions": {
                "operational_mode": {"enum": ["dev", "live"]},
            }
        }
    )
    root = intent_tree(enums_json=bad_enums)
    with pytest.raises(
        OperationalCapabilityTaxonomyError,
        match="missing or malformed 'fs_operation_class' enum",
    ):
        load_operational_capabilities(repo_root=root)


def test_missing_operational_mode_enum_raises(intent_tree: Callable[..., Path]) -> None:
    bad_enums = json.dumps(
        {
            "definitions": {
                "fs_operation_class": {"enum": ["read", "create", "modify", "delete"]},
            }
        }
    )
    root = intent_tree(enums_json=bad_enums)
    with pytest.raises(
        OperationalCapabilityTaxonomyError,
        match="missing or malformed 'operational_mode' enum",
    ):
        load_operational_capabilities(repo_root=root)
