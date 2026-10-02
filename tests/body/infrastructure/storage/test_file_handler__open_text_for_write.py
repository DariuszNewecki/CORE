"""FileHandler.open_text_for_write — governed streaming write (ADR-166 D4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from body.infrastructure.storage.file_handler import FileHandler


def test_streams_and_replaces_atomically(tmp_path: Path) -> None:
    fh = FileHandler(str(tmp_path))
    with fh.open_text_for_write("var/exports/claims.jsonl") as out:
        out.write('{"a": 1}\n')
        out.write('{"b": 2}\n')
    target = tmp_path / "var" / "exports" / "claims.jsonl"
    assert target.read_text() == '{"a": 1}\n{"b": 2}\n'
    assert not target.with_suffix(".jsonl.tmp").exists()


def test_failure_leaves_target_untouched_and_no_temp(tmp_path: Path) -> None:
    fh = FileHandler(str(tmp_path))
    target = tmp_path / "var" / "exports" / "claims.jsonl"
    target.parent.mkdir(parents=True)
    target.write_text("previous\n")
    with pytest.raises(RuntimeError):
        with fh.open_text_for_write("var/exports/claims.jsonl") as out:
            out.write("partial")
            raise RuntimeError("export failed midway")
    assert target.read_text() == "previous\n"
    assert not target.with_suffix(".jsonl.tmp").exists()


def test_refuses_python_targets(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        with FileHandler(str(tmp_path)).open_text_for_write("src/x.py"):
            pass


def test_refuses_intent_targets(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError
    ):  # ConstitutionalViolationError subclasses ValueError
        with FileHandler(str(tmp_path)).open_text_for_write(".intent/x.jsonl"):
            pass
    assert not (tmp_path / ".intent").exists()


def test_refuses_paths_outside_the_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(Exception):
        with FileHandler(str(repo)).open_text_for_write("../escape.jsonl"):
            pass
    assert not (tmp_path / "escape.jsonl").exists()
