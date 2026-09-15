"""shared.infrastructure.intent.machinery_floor_integrity -- #894 Condition 1.

The floor hash set is every shipped floor file except __pycache__/, with the
__init__.py markers INCLUDED (they ship with the floor and are floor content;
excluding a file class would leave an unverified slot inside .intent/).
Counts are derived from the manifest, never hardcoded (D-c).
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

from shared.infrastructure.intent.machinery_floor_integrity import (
    FloorIntegrityReport,
    find_collisions,
    floor_hash,
    floor_manifest,
    verify_floor,
)
from shared.infrastructure.intent.target_intent_assembly import assemble_target_intent


FLOOR = Path(str(importlib.resources.files("shared._machinery_floor")))


def test_manifest_covers_every_shipped_file_except_pycache() -> None:
    manifest = floor_manifest()
    on_disk = {
        p.relative_to(FLOOR).as_posix()
        for p in FLOOR.rglob("*")
        if p.is_file() and "__pycache__" not in p.relative_to(FLOOR).parts
    }
    assert set(manifest) == on_disk
    assert "__init__.py" in manifest, "package markers are floor content"
    assert not any("__pycache__" in rel for rel in manifest)
    assert all(len(h) == 64 for h in manifest.values())


def test_floor_hash_is_deterministic_and_content_sensitive() -> None:
    assert floor_hash() == floor_hash()
    assert len(floor_hash()) == 64


def test_verify_floor_clean_on_a_faithful_copy(tmp_path: Path) -> None:
    assembled = assemble_target_intent(tmp_path / ".intent")
    report = verify_floor(assembled.intent_root)
    assert isinstance(report, FloorIntegrityReport)
    assert report.clean, report.describe()
    assert set(report.ok) == set(floor_manifest())
    assert "all byte-identical" in report.describe()


def test_verify_floor_reports_one_modified_file(tmp_path: Path) -> None:
    root = assemble_target_intent(tmp_path / ".intent").intent_root
    target = root / "enforcement" / "config" / "action_risk.yaml"
    target.write_bytes(target.read_bytes() + b"\n# tampered\n")
    report = verify_floor(root)
    assert not report.clean
    assert report.modified == ("enforcement/config/action_risk.yaml",)
    assert report.missing == ()
    assert "modified: enforcement/config/action_risk.yaml" in report.describe()


def test_verify_floor_reports_one_missing_file(tmp_path: Path) -> None:
    root = assemble_target_intent(tmp_path / ".intent").intent_root
    (root / "META" / "enums.json").unlink()
    report = verify_floor(root)
    assert report.missing == ("META/enums.json",)
    assert report.modified == ()


def test_verify_floor_ignores_pycache_but_not_init_markers(tmp_path: Path) -> None:
    root = assemble_target_intent(tmp_path / ".intent").intent_root
    (root / "META" / "__pycache__").mkdir()
    (root / "META" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    assert verify_floor(root).clean
    (root / "META" / "__init__.py").write_text("# not the floor's marker\n")
    report = verify_floor(root)
    assert report.modified == ("META/__init__.py",)


def test_find_collisions_semantics(tmp_path: Path) -> None:
    """D-e: differing floor path -> collision; identical -> not; absent -> not."""
    subject_intent = tmp_path / "subject" / ".intent"
    (subject_intent / "META").mkdir(parents=True)
    # identical copy of one floor file
    (subject_intent / "META" / "enums.json").write_bytes(
        (FLOOR / "META" / "enums.json").read_bytes()
    )
    # differing copy of another
    (subject_intent / "META" / "vocabulary.json").write_bytes(b"{}")
    # a non-floor file the subject owns
    (subject_intent / "rules").mkdir()
    (subject_intent / "rules" / "mine.json").write_bytes(b"{}")
    assert find_collisions(subject_intent) == ["META/vocabulary.json"]


def test_find_collisions_no_intent_dir_is_empty(tmp_path: Path) -> None:
    assert find_collisions(tmp_path / "subject" / ".intent") == []
