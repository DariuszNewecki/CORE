# tests/mind/coherence/test_dispatch_parity.py
"""Unit tests for DispatchParityCheck (ADR-136 D2, P1-A sweep f3fc59b5).

DispatchParityCheck is pure data reading — no DB, no LLM, no async I/O
beyond the coroutine wrapper. Tests construct a minimal .intent/ tree in
tmp_path and verify the two sub-check verdicts.

Sub-check A (UNMAPPED): rule in .intent/rules/ but absent from mappings/.
Sub-check B (UNKNOWN_ENGINE): mapping entry references an engine that is
neither file-backed (a .py in src/mind/logic/engines/) nor in
.intent/taxonomies/substrate_enforcement.yaml.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from mind.coherence.checks.dispatch_parity import DispatchParityCheck


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_rules(rules_dir: Path, rule_ids: list[str]) -> None:
    rules_dir.mkdir(parents=True, exist_ok=True)
    data = {"rules": [{"id": rid, "enforcement": "blocking"} for rid in rule_ids]}
    (rules_dir / "test_rules.json").write_text(json.dumps(data), encoding="utf-8")


def _write_mapping(mappings_dir: Path, entries: dict[str, str]) -> None:
    """entries: {rule_id: engine_name}"""
    mappings_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "mappings": {rid: {"engine": engine} for rid, engine in entries.items()}
    }
    (mappings_dir / "test_mappings.yaml").write_text(yaml.dump(data), encoding="utf-8")


def _write_taxonomy(taxonomy_path: Path, entries: list[str]) -> None:
    taxonomy_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"entries": {e: {"description": "stub"} for e in entries}}
    taxonomy_path.write_text(yaml.dump(data), encoding="utf-8")


def _write_engines(engines_dir: Path, engine_names: list[str]) -> None:
    engines_dir.mkdir(parents=True, exist_ok=True)
    for name in engine_names:
        (engines_dir / f"{name}.py").write_text("# engine stub\n", encoding="utf-8")


def _make_check(tmp_path: Path) -> DispatchParityCheck:
    return DispatchParityCheck(repo_root=tmp_path)


# ---------------------------------------------------------------------------
# Sub-check A: UNMAPPED
# ---------------------------------------------------------------------------


async def test_unmapped_rule_produces_candidate(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["my.rule.id"])
    _write_mapping(tmp_path / ".intent" / "enforcement" / "mappings", {})
    _write_taxonomy(tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", [])
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", [])

    check = _make_check(tmp_path)
    candidates = await check.run()

    assert len(candidates) == 1
    assert "UNMAPPED" in candidates[0].claim
    assert "my.rule.id" in candidates[0].claim


async def test_mapped_rule_does_not_appear_in_unmapped(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["my.rule.id"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"my.rule.id": "ast_gate"},
    )
    _write_taxonomy(tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", [])
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", ["ast_gate"])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unmapped = [c for c in candidates if "UNMAPPED" in c.claim]
    assert unmapped == []


# ---------------------------------------------------------------------------
# Sub-check B: UNKNOWN_ENGINE
# ---------------------------------------------------------------------------


async def test_unknown_engine_in_mapping_produces_candidate(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["rule.x"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"rule.x": "ghost_engine"},
    )
    _write_taxonomy(tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", [])
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", [])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unknown = [c for c in candidates if "UNKNOWN_ENGINE" in c.claim]
    assert len(unknown) == 1
    assert "ghost_engine" in unknown[0].claim
    assert "rule.x" in unknown[0].claim


async def test_file_backed_engine_is_not_unknown(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["rule.x"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"rule.x": "ast_gate"},
    )
    _write_taxonomy(tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", [])
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", ["ast_gate"])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unknown = [c for c in candidates if "UNKNOWN_ENGINE" in c.claim]
    assert unknown == []


async def test_substrate_taxonomy_engine_is_not_unknown(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["rule.x"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"rule.x": "external_linter"},
    )
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml",
        ["external_linter"],
    )
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", [])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unknown = [c for c in candidates if "UNKNOWN_ENGINE" in c.claim]
    assert unknown == []


async def test_passive_gate_builtin_is_not_unknown(tmp_path: Path) -> None:
    """passive_gate is always in known_engines regardless of taxonomy."""
    _write_rules(tmp_path / ".intent" / "rules", ["rule.x"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"rule.x": "passive_gate"},
    )
    _write_taxonomy(tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", [])
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", [])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unknown = [c for c in candidates if "UNKNOWN_ENGINE" in c.claim]
    assert unknown == []


# ---------------------------------------------------------------------------
# Clean pass
# ---------------------------------------------------------------------------


async def test_clean_intent_tree_returns_no_candidates(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["rule.a", "rule.b"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"rule.a": "ast_gate", "rule.b": "passive_gate"},
    )
    _write_taxonomy(tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", [])
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", ["ast_gate"])

    check = _make_check(tmp_path)
    candidates = await check.run()

    assert candidates == []


async def test_empty_rules_directory_returns_no_candidates(tmp_path: Path) -> None:
    (tmp_path / ".intent" / "rules").mkdir(parents=True, exist_ok=True)
    _write_mapping(tmp_path / ".intent" / "enforcement" / "mappings", {})
    _write_taxonomy(tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", [])
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", [])

    check = _make_check(tmp_path)
    candidates = await check.run()

    assert candidates == []
