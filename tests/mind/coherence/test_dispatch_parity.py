# tests/mind/coherence/test_dispatch_parity.py
"""Unit tests for DispatchParityCheck (ADR-136 D2, P1-A sweep f3fc59b5).

DispatchParityCheck is pure data reading — no DB, no LLM, no async I/O
beyond the coroutine wrapper. Tests construct a minimal .intent/ tree in
tmp_path and verify the two sub-check verdicts.

Sub-check A (UNMAPPED): rule in .intent/rules/ but absent from mappings/.
Sub-check B (UNKNOWN_ENGINE): mapping entry references an engine that is
neither file-backed (a .py or package dir in src/mind/logic/engines/) nor
in .intent/taxonomies/substrate_enforcement.yaml.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from mind.coherence.checks.dispatch_parity import DispatchParityCheck


# ---------------------------------------------------------------------------
# Stub IntentRepository
# ---------------------------------------------------------------------------


@dataclass
class _RuleRef:
    rule_id: str
    content: dict[str, Any]


# ID: b78c853c-7624-46f7-8de9-c8044610f7aa
class _StubIntentRepo:
    """Minimal IntentRepository stub backed by files in tmp_path.

    Reads rules from .intent/rules/**/*.json and mappings from
    .intent/enforcement/mappings/**/*.yaml, matching the real repo's
    two-field contract consumed by DispatchParityCheck.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    # ID: 56a78422-3c67-4f2c-a636-dc1932b5e3b5
    def known_rule_ids(self) -> set[str]:
        rules_dir = self._root / ".intent" / "rules"
        ids: set[str] = set()
        for path in rules_dir.rglob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            for rule in data.get("rules", []):
                if isinstance(rule, dict) and "id" in rule:
                    ids.add(rule["id"])
        return ids

    # ID: d0730d2f-335b-4a66-a45b-5cc21ba72522
    def get_rule(self, rule_id: str) -> _RuleRef:
        rules_dir = self._root / ".intent" / "rules"
        for path in rules_dir.rglob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            for rule in data.get("rules", []):
                if isinstance(rule, dict) and rule.get("id") == rule_id:
                    return _RuleRef(rule_id=rule_id, content=rule)
        raise KeyError(rule_id)

    # ID: f71c3a5e-9efc-4393-bef7-e608817bc50b
    def iter_documents(self) -> Iterator[tuple[Path, dict]]:
        intent_root = self._root / ".intent"
        for path in intent_root.rglob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                yield path.relative_to(intent_root), data
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_rules(
    rules_dir: Path,
    rule_ids: list[str],
    enforcement: str = "blocking",
) -> None:
    rules_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "rules": [{"id": rid, "enforcement": enforcement} for rid in rule_ids]
    }
    (rules_dir / "test_rules.json").write_text(json.dumps(data), encoding="utf-8")


def _write_mapping(mappings_dir: Path, entries: dict[str, str]) -> None:
    """entries: {rule_id: engine_name}"""
    mappings_dir.mkdir(parents=True, exist_ok=True)
    data = {"mappings": {rid: {"engine": engine} for rid, engine in entries.items()}}
    (mappings_dir / "test_mappings.yaml").write_text(yaml.dump(data), encoding="utf-8")


def _write_taxonomy(taxonomy_path: Path, entries: list[str]) -> None:
    taxonomy_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"entries": {e: {"description": "stub"} for e in entries}}
    taxonomy_path.write_text(yaml.dump(data), encoding="utf-8")


def _write_engines(engines_dir: Path, flat_names: list[str]) -> None:
    """Create flat .py engine stubs."""
    engines_dir.mkdir(parents=True, exist_ok=True)
    for name in flat_names:
        (engines_dir / f"{name}.py").write_text("# engine stub\n", encoding="utf-8")


def _write_package_engines(engines_dir: Path, pkg_names: list[str]) -> None:
    """Create package-style engine stubs (directories with __init__.py)."""
    engines_dir.mkdir(parents=True, exist_ok=True)
    for name in pkg_names:
        pkg_dir = engines_dir / name
        pkg_dir.mkdir(exist_ok=True)
        (pkg_dir / "__init__.py").write_text("# engine package stub\n", encoding="utf-8")


def _make_check(tmp_path: Path) -> DispatchParityCheck:
    return DispatchParityCheck(
        repo_root=tmp_path, intent_repo=_StubIntentRepo(tmp_path)
    )


# ---------------------------------------------------------------------------
# Sub-check A: UNMAPPED
# ---------------------------------------------------------------------------


async def test_unmapped_rule_produces_candidate(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["my.rule.id"])
    _write_mapping(tmp_path / ".intent" / "enforcement" / "mappings", {})
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
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
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", ["ast_gate"])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unmapped = [c for c in candidates if "UNMAPPED" in c.claim]
    assert unmapped == []


async def test_advisory_rule_without_mapping_is_not_unmapped(tmp_path: Path) -> None:
    """Retired advisory rules with intentionally-removed mappings must not fire."""
    _write_rules(
        tmp_path / ".intent" / "rules",
        ["legacy.retired.rule"],
        enforcement="advisory",
    )
    _write_mapping(tmp_path / ".intent" / "enforcement" / "mappings", {})
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", [])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unmapped = [c for c in candidates if "UNMAPPED" in c.claim]
    assert unmapped == [], "Advisory rules with no mapping must not produce UNMAPPED"


# ---------------------------------------------------------------------------
# Sub-check B: UNKNOWN_ENGINE
# ---------------------------------------------------------------------------


async def test_unknown_engine_in_mapping_produces_candidate(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["rule.x"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"rule.x": "ghost_engine"},
    )
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", [])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unknown = [c for c in candidates if "UNKNOWN_ENGINE" in c.claim]
    assert len(unknown) == 1
    assert "ghost_engine" in unknown[0].claim
    assert "rule.x" in unknown[0].claim


async def test_flat_file_engine_is_not_unknown(tmp_path: Path) -> None:
    _write_rules(tmp_path / ".intent" / "rules", ["rule.x"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"rule.x": "ast_gate"},
    )
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", ["ast_gate"])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unknown = [c for c in candidates if "UNKNOWN_ENGINE" in c.claim]
    assert unknown == []


async def test_package_engine_is_not_unknown(tmp_path: Path) -> None:
    """cli_gate / workflow_gate are packages — must be recognised as file-backed."""
    _write_rules(tmp_path / ".intent" / "rules", ["cli.my_rule", "wf.my_rule"])
    _write_mapping(
        tmp_path / ".intent" / "enforcement" / "mappings",
        {"cli.my_rule": "cli_gate", "wf.my_rule": "workflow_gate"},
    )
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
    engines_dir = tmp_path / "src" / "mind" / "logic" / "engines"
    _write_package_engines(engines_dir, ["cli_gate", "workflow_gate"])

    check = _make_check(tmp_path)
    candidates = await check.run()

    unknown = [c for c in candidates if "UNKNOWN_ENGINE" in c.claim]
    assert unknown == [], f"Package engines falsely flagged: {[c.claim for c in unknown]}"


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
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
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
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", ["ast_gate"])

    check = _make_check(tmp_path)
    candidates = await check.run()

    assert candidates == []


async def test_empty_rules_directory_returns_no_candidates(tmp_path: Path) -> None:
    (tmp_path / ".intent" / "rules").mkdir(parents=True, exist_ok=True)
    _write_mapping(tmp_path / ".intent" / "enforcement" / "mappings", {})
    _write_taxonomy(
        tmp_path / ".intent" / "taxonomies" / "substrate_enforcement.yaml", []
    )
    _write_engines(tmp_path / "src" / "mind" / "logic" / "engines", [])

    check = _make_check(tmp_path)
    candidates = await check.run()

    assert candidates == []
