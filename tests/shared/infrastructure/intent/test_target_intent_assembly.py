"""shared.infrastructure.intent.target_intent_assembly -- #894 D-b / Condition 1.

Floor + additive overlay, refusing any overlay path that is a floor path,
never assembling into an existing directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.machinery_floor_integrity import (
    floor_hash,
    floor_manifest,
    verify_floor,
)
from shared.infrastructure.intent.target_intent_assembly import (
    OverlayCollisionError,
    assemble_target_intent,
    overlay_hash,
)


def _overlay(tmp_path: Path) -> Path:
    o = tmp_path / "overlay"
    (o / "rules" / "code").mkdir(parents=True)
    (o / "rules" / "code" / "mine.json").write_text('{"rules": []}\n')
    (o / "enforcement" / "config").mkdir(parents=True)
    (o / "enforcement" / "config" / "safe_auto_approval_envelope.yaml").write_text(
        "safe_auto_approval_envelope:\n  authorized_actions: [fix.format]\n"
        "  authorized_path_prefixes: [package/]\n  authorized_extensions: [.py]\n"
    )
    (o / "__pycache__").mkdir()
    (o / "__pycache__" / "junk.pyc").write_bytes(b"\x00")
    return o


def test_floor_only_assembly_is_clean_and_hashes_match(tmp_path: Path) -> None:
    assembled = assemble_target_intent(tmp_path / ".intent")
    assert verify_floor(assembled.intent_root).clean
    assert assembled.floor_hash == floor_hash()
    assert assembled.overlay_hash == overlay_hash(None)
    assert assembled.overlay_files == ()


def test_overlay_is_added_additively_and_floor_stays_clean(tmp_path: Path) -> None:
    assembled = assemble_target_intent(tmp_path / ".intent", _overlay(tmp_path))
    assert verify_floor(assembled.intent_root).clean
    assert set(assembled.overlay_files) == {
        "rules/code/mine.json",
        "enforcement/config/safe_auto_approval_envelope.yaml",
    }
    assert (assembled.intent_root / "rules" / "code" / "mine.json").is_file()
    assert not (assembled.intent_root / "__pycache__").exists()
    assert assembled.overlay_hash == overlay_hash(_overlay(tmp_path / "again"))


def test_overlay_naming_a_floor_path_is_refused_before_any_write(
    tmp_path: Path,
) -> None:
    o = _overlay(tmp_path)
    (o / "enforcement" / "config" / "action_risk.yaml").write_text("actions: {}\n")
    with pytest.raises(OverlayCollisionError, match=r"action_risk\.yaml"):
        assemble_target_intent(tmp_path / ".intent", o)
    assert not (tmp_path / ".intent").exists(), "refused before writing anything"


def test_overlay_may_not_replace_a_floor_init_marker(tmp_path: Path) -> None:
    o = _overlay(tmp_path)
    (o / "META").mkdir()
    (o / "META" / "__init__.py").write_text("")
    with pytest.raises(OverlayCollisionError, match=r"META/__init__\.py"):
        assemble_target_intent(tmp_path / ".intent", o)


def test_existing_destination_is_refused(tmp_path: Path) -> None:
    (tmp_path / ".intent").mkdir()
    with pytest.raises(FileExistsError):
        assemble_target_intent(tmp_path / ".intent")


def test_missing_overlay_dir_is_refused(tmp_path: Path) -> None:
    with pytest.raises(OverlayCollisionError, match="not found"):
        assemble_target_intent(tmp_path / ".intent", tmp_path / "nope")


def test_manifest_count_is_derived_not_hardcoded(tmp_path: Path) -> None:
    assembled = assemble_target_intent(tmp_path / ".intent")
    copied = {
        p.relative_to(assembled.intent_root).as_posix()
        for p in assembled.intent_root.rglob("*")
        if p.is_file()
    }
    assert copied == set(floor_manifest())
