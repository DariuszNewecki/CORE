# tests/body/infrastructure/storage/test_file_handler__intent_traversal.py

"""#949: a path that merely STARTS in scratch cannot reach .intent/.

FileHandler used to classify the caller's raw spelling, so
``var/tmp/../../.intent/x`` was "ephemeral-scratch", and IntentGuard skipped
scratch paths before its absolute .intent/ block. These tests run the real
FileHandler against a real IntentGuard (no policy rules; only the vocabulary
projection is short-circuited, as in the dispatch unit tests) on a real
repository under var/tmp/, across every guarded entry point: write, streaming
write, remove, ensure_dir, remove_tree, copy_tree, create_symlink. Traversal,
in-repo symlinks and absolute spellings must all be refused before mutation;
genuine scratch keeps its exemption; a path landing in src/ gets repo-source
treatment again.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from body.governance.intent_guard import IntentGuard
from body.infrastructure.storage.file_handler import FileHandler
from mind.governance.violation_report import ConstitutionalViolationError


INTENT_TRAVERSALS = [
    ".intent/probe.json",
    "var/tmp/../../.intent/probe.json",
    "work/../.intent/probe.json",
    "src/../.intent/probe.json",
    "./var/tmp/x/../../../.intent/probe.json",
]


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    var_tmp = Path(__file__).resolve().parents[4] / "var" / "tmp"
    var_tmp.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="fh_intent_traversal_", dir=str(var_tmp)))
    for d in (".intent/rules", "var/tmp", "work", "src"):
        (root / d).mkdir(parents=True)
    (root / ".intent/rules/law.json").write_text("{}\n")
    monkeypatch.setattr(
        "body.governance.intent_guard.load_vocabulary_projection",
        lambda _repo_path: {},
    )
    try:
        yield root.resolve()
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def fh(repo: Path) -> FileHandler:
    handler = FileHandler(str(repo))
    guard = IntentGuard.__new__(IntentGuard)
    guard.repo_path = repo
    guard.intent_root = repo / ".intent"
    guard.rules = []
    guard.strict_mode = False
    guard._capabilities = None
    handler._guard = guard
    return handler


def _intent_files(repo: Path) -> list[str]:
    return sorted(p.relative_to(repo).as_posix() for p in (repo / ".intent").rglob("*"))


@pytest.mark.parametrize("path", INTENT_TRAVERSALS)
def test_write_into_intent_is_refused_however_spelled(
    fh: FileHandler, repo: Path, path: str
) -> None:
    before = _intent_files(repo)
    with pytest.raises(ConstitutionalViolationError):
        fh.write(path, "{}\n")
    assert _intent_files(repo) == before


@pytest.mark.parametrize("path", INTENT_TRAVERSALS)
def test_streaming_write_into_intent_is_refused(
    fh: FileHandler, repo: Path, path: str
) -> None:
    before = _intent_files(repo)
    with pytest.raises(ConstitutionalViolationError):
        with fh.open_text_for_write(path) as handle:
            handle.write("{}\n")
    assert _intent_files(repo) == before


def test_absolute_spelling_into_intent_is_refused(fh: FileHandler, repo: Path) -> None:
    with pytest.raises(ConstitutionalViolationError):
        fh.write(str(repo / "var/tmp/../../.intent/probe.json"), "{}\n")
    assert not (repo / ".intent/probe.json").exists()


def test_in_repo_symlink_from_scratch_into_intent_is_refused(
    fh: FileHandler, repo: Path
) -> None:
    (repo / "var/tmp/link").symlink_to(repo / ".intent")
    with pytest.raises(ConstitutionalViolationError):
        fh.write("var/tmp/link/probe.json", "{}\n")
    assert not (repo / ".intent/probe.json").exists()


def test_remove_via_traversal_is_refused(fh: FileHandler, repo: Path) -> None:
    with pytest.raises(ConstitutionalViolationError):
        fh.remove_file("var/tmp/../../.intent/rules/law.json")
    assert (repo / ".intent/rules/law.json").exists()


def test_directory_operations_via_traversal_are_refused(
    fh: FileHandler, repo: Path
) -> None:
    (repo / "var/tmp/src_tree").mkdir()
    (repo / "var/tmp/src_tree/f.txt").write_text("x\n")
    with pytest.raises(ConstitutionalViolationError):
        fh.ensure_dir("var/tmp/../../.intent/newdir")
    with pytest.raises(ConstitutionalViolationError):
        fh.remove_tree("work/../.intent/rules")
    with pytest.raises(ConstitutionalViolationError):
        fh.copy_tree("var/tmp/src_tree", "var/tmp/../../.intent/copied")
    assert not (repo / ".intent/newdir").exists()
    assert not (repo / ".intent/copied").exists()
    assert (repo / ".intent/rules/law.json").exists()


def test_symlink_creation_via_traversal_is_refused(fh: FileHandler, repo: Path) -> None:
    with pytest.raises(ConstitutionalViolationError):
        fh.create_symlink("var/tmp/../../.intent/link", repo / "src")
    assert not (repo / ".intent/link").is_symlink()


def test_genuine_scratch_keeps_its_exemption(fh: FileHandler, repo: Path) -> None:
    """Scratch skips source transforms: invalid Python lands as-is."""
    result = fh.write("var/tmp/run/broken.py", "def (:\n")
    assert result.status == "success"
    assert result.detail == "var/tmp/run/broken.py"
    assert (repo / "var/tmp/run/broken.py").read_text() == "def (:\n"


def test_path_landing_in_src_gets_repo_source_treatment(
    fh: FileHandler, repo: Path
) -> None:
    """Classified by destination: the syntax check applies again."""
    with pytest.raises(ValueError, match="Syntax Error"):
        fh.write("var/tmp/../../src/m.py", "def (:\n")
    assert not (repo / "src/m.py").exists()
    result = fh.write("var/tmp/../../src/m.py", "x = 1\n")
    assert result.detail == "src/m.py"
    assert (repo / "src/m.py").read_text() == "x = 1\n"
