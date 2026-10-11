"""Law apply: reading a proposal into memory, and the D5 warnings CORE computes."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from body.governance.law_custody.law_warnings import compute_warnings
from body.governance.law_custody.proposal import (
    ProposalError,
    parse_declared_warnings,
    parse_removals,
    read_proposal,
)


GOVERNED = (
    ".intent/",
    ".specs/",
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/hooks/",
)


def _proposal(tmp_path: Path, md: str, files: dict[str, bytes]) -> Path:
    root = tmp_path / "law-proposals" / "0001-test"
    (root / "files").mkdir(parents=True)
    (root / "proposal.md").write_text(md, encoding="utf-8")
    for rel, content in files.items():
        target = root / "files" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return tmp_path / "law-proposals"


MD = """# Proposal 0001

## Declared warnings

1. ADR-1's meaning changes:
   the gate is redefined.
2. Scope widened.

## Remove

- `.specs/old.md` (superseded)

## Approval

(pending)
"""


def test_reads_files_removals_and_declared_warnings(tmp_path: Path) -> None:
    proposals = _proposal(tmp_path, MD, {".specs/new.md": b"hello\n"})
    proposal = read_proposal(proposals, "0001-test", GOVERNED)
    assert [f.path for f in proposal.files] == [".specs/new.md"]
    assert proposal.removals == (".specs/old.md",)
    assert proposal.declared_warnings == (
        "ADR-1's meaning changes: the gate is redefined.",
        "Scope widened.",
    )
    assert proposal.paths() == [".specs/new.md", ".specs/old.md"]
    assert len(proposal.digest) == 64


def test_editing_the_folder_after_reading_changes_nothing(tmp_path: Path) -> None:
    proposals = _proposal(tmp_path, MD, {".specs/new.md": b"hello\n"})
    proposal = read_proposal(proposals, "0001-test", GOVERNED)
    (proposals / "0001-test" / "files" / ".specs" / "new.md").write_bytes(b"evil\n")
    assert proposal.files[0].content == b"hello\n"


def test_digest_changes_with_any_byte(tmp_path: Path) -> None:
    proposals = _proposal(tmp_path, MD, {".specs/new.md": b"hello\n"})
    first = read_proposal(proposals, "0001-test", GOVERNED).digest
    (proposals / "0001-test" / "files" / ".specs" / "new.md").write_bytes(b"hello!\n")
    assert read_proposal(proposals, "0001-test", GOVERNED).digest != first


@pytest.mark.parametrize("bad_id", ["../x", "a/b", "", ".hidden"])
def test_refuses_ids_that_are_paths(tmp_path: Path, bad_id: str) -> None:
    proposals = _proposal(tmp_path, MD, {".specs/new.md": b"x"})
    with pytest.raises(ProposalError):
        read_proposal(proposals, bad_id, GOVERNED)


def test_refuses_non_governed_paths(tmp_path: Path) -> None:
    proposals = _proposal(tmp_path, "# p\n", {"src/evil.py": b"x"})
    with pytest.raises(ProposalError, match="not governed text"):
        read_proposal(proposals, "0001-test", GOVERNED)


def test_refuses_symlinks(tmp_path: Path) -> None:
    proposals = _proposal(tmp_path, "# p\n", {".specs/a.md": b"x"})
    os.symlink("/etc/passwd", proposals / "0001-test" / "files" / ".specs" / "b.md")
    with pytest.raises(ProposalError, match="regular file"):
        read_proposal(proposals, "0001-test", GOVERNED)


def test_refuses_empty_and_write_plus_remove(tmp_path: Path) -> None:
    proposals = _proposal(tmp_path, "# p\n", {})
    with pytest.raises(ProposalError, match="nothing"):
        read_proposal(proposals, "0001-test", GOVERNED)
    md = "# p\n\n## Remove\n\n- `.specs/a.md`\n"
    proposals = _proposal(tmp_path / "2", md, {".specs/a.md": b"x"})
    with pytest.raises(ProposalError, match="written and removed"):
        read_proposal(proposals, "0001-test", GOVERNED)


def test_remove_item_without_path_is_refused() -> None:
    with pytest.raises(ProposalError):
        parse_removals("## Remove\n\n- nothing to see\n")
    assert parse_removals("Remove: nothing.\n") == ()
    assert parse_declared_warnings("# no such section\n") == ()


def _rules(*rules: tuple[str, str]) -> bytes:
    return json.dumps(
        {"rules": [{"id": rid, "enforcement": level} for rid, level in rules]}
    ).encode()


def test_rule_added_removed_and_weakened() -> None:
    path = ".intent/rules/architecture/x.json"
    old = {path: _rules(("a", "blocking"), ("b", "reporting"))}
    new = {path: _rules(("a", "reporting"), ("c", "advisory"))}
    found = {(w.category, w.weakening) for w in compute_warnings(old, new)}
    assert ("enforcement_changed", True) in found
    assert ("rule_removed", True) in found
    assert ("rule_added", False) in found


def test_raising_a_level_is_not_weakening() -> None:
    path = ".intent/rules/architecture/x.json"
    warnings = compute_warnings(
        {path: _rules(("a", "reporting"))}, {path: _rules(("a", "blocking"))}
    )
    assert [(w.category, w.weakening) for w in warnings] == [
        ("enforcement_changed", False)
    ]


def test_excludes_added_and_applies_to_narrowed() -> None:
    path = ".intent/enforcement/mappings/architecture/x.yaml"
    old = {
        path: b"""
mappings:
  rule.one:
    engine: ast_gate
    scope:
      applies_to: ["src/**/*.py", "features/**/*.py"]
      excludes: []
"""
    }
    new = {
        path: b"""
mappings:
  rule.one:
    engine: ast_gate
    scope:
      applies_to: ["src/**/*.py"]
      excludes: ["src/body/x.py"]
"""
    }
    categories = [w.category for w in compute_warnings(old, new)]
    assert categories == ["exclude_added", "applies_to_narrowed"]


def test_constitutional_core_and_contract_listed_first() -> None:
    new = {
        ".intent/rules/governance/g.json": _rules(("g", "blocking")),
        "CLAUDE.md": b"new",
        ".specs/x.md": b"x",
    }
    warnings = compute_warnings({}, new)
    assert [w.category for w in warnings][:2] == [
        "constitutional_core",
        "assistant_contract",
    ]


def test_unchanged_paths_raise_nothing() -> None:
    same = {".intent/rules/governance/g.json": _rules(("g", "blocking"))}
    assert compute_warnings(same, dict(same)) == []
