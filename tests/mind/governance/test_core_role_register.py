# tests/mind/governance/test_core_role_register.py
"""``CORE_ROLE`` declarations in ``src/`` must match the governed register (#1125).

A module-level ``CORE_ROLE = "facade" | "algorithm" | "catalog"`` (ADR-095 D3)
makes ``modularity.needs_split`` and ``modularity.class_too_large`` skip the
file. ``.intent/enforcement/config/core_role_register.yaml`` lists every file
allowed to carry it. This test fails when ``src/`` and the register disagree in
either direction or on the value, so a new self-exemption is a visible change
to governed text.

Detection is wider than the exemption check: any top-level assignment to
``CORE_ROLE`` (plain or annotated, any value) counts as a declaration.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
_REGISTER = _REPO_ROOT / ".intent/enforcement/config/core_role_register.yaml"


def _declared_role(tree: ast.Module) -> str | None:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == "CORE_ROLE" for t in targets):
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
            return ast.unparse(value)
    return None


def _declarations() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted(_SRC.rglob("*.py")):
        role = _declared_role(ast.parse(path.read_text(encoding="utf-8")))
        if role is not None:
            found[path.relative_to(_REPO_ROOT).as_posix()] = role
    return found


def _register() -> dict[str, dict[str, str]]:
    data = yaml.safe_load(_REGISTER.read_text(encoding="utf-8"))
    return data["files"]


# ID: e83864a2-709f-47a1-a4f7-484d757b3176
def test_register_entries_are_well_formed() -> None:
    for rel, entry in _register().items():
        assert set(entry) == {"role", "reason"}, rel
        assert entry["role"] in {"facade", "algorithm", "catalog"}, rel
        assert str(entry["reason"]).strip(), rel


# ID: 8c9a8559-d96b-4a17-99a0-7a12226e7a44
def test_core_role_declarations_match_register() -> None:
    declared = _declarations()
    registered = {rel: entry["role"] for rel, entry in _register().items()}

    unlisted = sorted(set(declared) - set(registered))
    stale = sorted(set(registered) - set(declared))
    mismatched = sorted(
        f"{rel}: declares {declared[rel]!r}, register says {registered[rel]!r}"
        for rel in set(declared) & set(registered)
        if declared[rel] != registered[rel]
    )

    assert not unlisted, (
        "CORE_ROLE declared but not in core_role_register.yaml "
        f"(a self-exemption from the size checks needs a register entry): {unlisted}"
    )
    assert not stale, f"register lists files that no longer declare CORE_ROLE: {stale}"
    assert not mismatched, f"CORE_ROLE value differs from the register: {mismatched}"


# ID: f04d2437-391c-4dd6-86fd-8d7cad7c0e35
def test_detection_covers_plain_and_annotated_assignments() -> None:
    assert _declared_role(ast.parse('CORE_ROLE = "facade"')) == "facade"
    assert _declared_role(ast.parse('CORE_ROLE: str = "catalog"')) == "catalog"
    assert _declared_role(ast.parse("CORE_ROLE = ROLE")) == "ROLE"
    assert _declared_role(ast.parse('def f():\n    CORE_ROLE = "facade"')) is None
