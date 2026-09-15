"""shared.infrastructure.intent.target_intent_assembly -- #894 D-b / Condition 1.

Floor + additive overlay, refusing any overlay path that is a floor path,
never assembling into an existing directory.
"""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.intent.machinery_floor_integrity import (
    floor_hash,
    floor_manifest,
    verify_floor,
)
from shared.infrastructure.intent.target_intent_assembly import (
    OverlayCollisionError,
    SubjectCopyError,
    assemble_target_intent,
    materialize_execution_copy,
    overlay_hash,
    subject_fingerprint,
)


FLOOR = Path(str(importlib.resources.files("shared._machinery_floor")))


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


# --- Unit 2: execution copy (Condition 2 + collision rule) ---------------------


def _subject(tmp_path: Path, *, with_intent: bool, collide: bool = False) -> Path:
    """A synthetic frozen subject: a git repo with a package, an executable
    script, a symlink (pointing OUTSIDE the subject), and optionally a
    .intent/ carrying some floor files (some identical, some differing)."""
    s = tmp_path / "subject"
    (s / "package").mkdir(parents=True)
    (s / "package" / "mod.py").write_text("x = 1\n")
    script = s / "run.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    os.symlink("/etc/hostname", s / "outside_link")
    if with_intent:
        (s / ".intent" / "META").mkdir(parents=True)
        (s / ".intent" / "rules" / "code").mkdir(parents=True)
        (s / ".intent" / "META" / "enums.json").write_bytes(
            (FLOOR / "META" / "enums.json").read_bytes()
        )  # identical
        (s / ".intent" / "rules" / "code" / "subject_rule.json").write_text("{}\n")
        if collide:
            (s / ".intent" / "META" / "vocabulary.json").write_bytes(b'{"old": true}\n')
            (s / ".intent" / "enforcement" / "config").mkdir(parents=True)
            (s / ".intent" / "enforcement" / "config" / "action_risk.yaml").write_text(
                "actions: {}\n"
            )
    subprocess.run(["git", "init", "-q"], cwd=s, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
        cwd=s,
        check=True,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "s"],
        cwd=s,
        check=True,
    )
    return s


def test_fingerprint_sees_content_mode_and_symlink_text_but_never_follows(
    tmp_path: Path,
) -> None:
    s = _subject(tmp_path, with_intent=False)
    f0 = subject_fingerprint(s)
    assert f0 == subject_fingerprint(s)
    # chmod only -> changes
    (s / "run.sh").chmod(0o644)
    f1 = subject_fingerprint(s)
    assert f1 != f0
    # symlink target text changes -> changes; the link is never followed
    (s / "outside_link").unlink()
    os.symlink("/etc/passwd", s / "outside_link")
    assert subject_fingerprint(s) != f1
    # a dangling link is fine (never dereferenced)
    (s / "outside_link").unlink()
    os.symlink("/nonexistent/nowhere", s / "outside_link")
    subject_fingerprint(s)
    # .git is excluded: a commit doesn't change the fingerprint
    before = subject_fingerprint(s)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
        cwd=s,
        check=True,
    )
    assert subject_fingerprint(s) == before


def test_fingerprint_refuses_special_files(tmp_path: Path) -> None:
    s = _subject(tmp_path, with_intent=False)
    os.mkfifo(s / "pipe")
    with pytest.raises(SubjectCopyError, match="special"):
        subject_fingerprint(s)


def test_execution_copy_subject_without_intent_gets_floor_and_overlay(
    tmp_path: Path,
) -> None:
    s = _subject(tmp_path, with_intent=False)
    before = subject_fingerprint(s)
    run = tmp_path / "run"
    copy = materialize_execution_copy(s, run, _overlay(tmp_path))
    assert copy.target_root == run / "target" and copy.evidence_root == run / "evidence"
    assert verify_floor(copy.intent_root).clean
    assert copy.displaced == ()
    assert (copy.target_root / "package" / "mod.py").read_text() == "x = 1\n"
    # symlink preserved as a link with the same text; executable bit preserved
    assert (copy.target_root / "outside_link").is_symlink()
    assert os.readlink(copy.target_root / "outside_link") == "/etc/hostname"
    assert (copy.target_root / "run.sh").stat().st_mode & stat.S_IXUSR
    assert not (copy.target_root / ".git").exists()
    assert subject_fingerprint(s) == before, "the frozen subject is never written"
    manifest = json.loads(copy.collision_manifest_path.read_text())
    assert manifest["displaced"] == [] and manifest["floor_hash"] == floor_hash()


def test_execution_copy_floor_wins_and_preserves_displaced_originals(
    tmp_path: Path,
) -> None:
    s = _subject(tmp_path, with_intent=True, collide=True)
    before = subject_fingerprint(s)
    copy = materialize_execution_copy(s, tmp_path / "run")
    assert verify_floor(copy.intent_root).clean
    displaced = {d.path: d for d in copy.displaced}
    assert set(displaced) == {
        "META/vocabulary.json",
        "enforcement/config/action_risk.yaml",
    }
    # identical floor file was left, not displaced; subject's own rule survives
    assert "META/enums.json" not in displaced
    assert (
        copy.intent_root / "rules" / "code" / "subject_rule.json"
    ).read_text() == "{}\n"
    # originals preserved byte-for-byte under evidence/displaced
    kept = copy.evidence_root / "displaced" / "META" / "vocabulary.json"
    assert kept.read_bytes() == b'{"old": true}\n'
    assert (
        displaced["META/vocabulary.json"].original_sha256
        == hashlib.sha256(b'{"old": true}\n').hexdigest()
    )
    assert (
        displaced["META/vocabulary.json"].installed_floor_sha256
        == floor_manifest()["META/vocabulary.json"]
    )
    # deterministic manifest, sorted by path
    m = json.loads(copy.collision_manifest_path.read_text())
    assert [d["path"] for d in m["displaced"]] == sorted(displaced)
    assert subject_fingerprint(s) == before


def test_execution_copy_refuses_overlay_colliding_with_subject_law(
    tmp_path: Path,
) -> None:
    s = _subject(tmp_path, with_intent=True)
    o = tmp_path / "overlay"
    (o / "rules" / "code").mkdir(parents=True)
    (o / "rules" / "code" / "subject_rule.json").write_text(
        "{}\n"
    )  # same path as subject's
    with pytest.raises(OverlayCollisionError, match="no ruling chooses a winner"):
        materialize_execution_copy(s, tmp_path / "run", o)


def test_execution_copy_refuses_non_regular_file_at_floor_path(tmp_path: Path) -> None:
    s = _subject(tmp_path, with_intent=True)
    os.symlink("enums.json", s / ".intent" / "META" / "vocabulary.json")
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
        cwd=s,
        check=True,
    )
    with pytest.raises(SubjectCopyError, match="non-regular"):
        materialize_execution_copy(s, tmp_path / "run")


def test_execution_copy_refuses_existing_run_root(tmp_path: Path) -> None:
    s = _subject(tmp_path, with_intent=False)
    (tmp_path / "run").mkdir()
    with pytest.raises(FileExistsError):
        materialize_execution_copy(s, tmp_path / "run")
