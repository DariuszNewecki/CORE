"""Regression suite for FileHandler.write — the unified write entry (ADR-097 D4).

Pins the per-target-class behavior matrix from ADR-097 D3 as observed
through the new write() method:

- repo-source: syntax check on .py; # ID: anchor injection; trailing newline.
- runtime-output: trailing newline for text; no source-shape transforms.
- ephemeral-scratch: trailing newline for text; NO syntax check, NO ID
  anchors. The substring-bug case (var/tmp/.../src/foo.py) classifies
  here, structurally foreclosing the bug ADR-097 D2 names.
- governed-artifact: today the .intent/ hard invariant blocks src/ writes
  (legacy behavior); the API-mediated tier ships in ADR-097 step 6. Not
  exercised here because the test harness stubs the guard.

IntentGuard is stubbed (same pattern as tests/shared/test_file_handler__regression_matrix.py).
This suite pins post-guard behavior; guard semantics are pinned in
the IntentGuard regression suite (test_intent_guard__target_class_dispatch.py).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from shared.infrastructure.storage.file_handler import FileHandler, FileOpResult


def _repo_var_tmp() -> Path:
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    var_tmp = repo_root / "var" / "tmp"
    var_tmp.mkdir(parents=True, exist_ok=True)
    return var_tmp


@pytest.fixture
def repo_root() -> Path:
    d = Path(tempfile.mkdtemp(prefix="fh_write_unified_", dir=str(_repo_var_tmp())))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fh(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> FileHandler:
    handler = FileHandler(str(repo_root))
    monkeypatch.setattr(handler, "_guard_paths", lambda *a, **kw: None)
    return handler


# ---------------------------------------------------------------------------
# Return shape + atomic-write contract
# ---------------------------------------------------------------------------


def test_write_returns_filopresult(fh: FileHandler, repo_root: Path) -> None:
    result = fh.write("reports/note.txt", "hello")
    assert isinstance(result, FileOpResult)
    assert result.status == "success"
    assert result.message == "Wrote file"
    assert result.detail == "reports/note.txt"


def test_write_creates_parent_directories(fh: FileHandler, repo_root: Path) -> None:
    fh.write("reports/audit/2026/x.json", '{"k": 1}')
    assert (repo_root / "reports" / "audit" / "2026" / "x.json").exists()


def test_write_strips_dot_slash_prefix(fh: FileHandler, repo_root: Path) -> None:
    fh.write("./reports/p.txt", "x")
    assert (repo_root / "reports" / "p.txt").exists()


def test_write_overwrites_existing_atomically(
    fh: FileHandler, repo_root: Path
) -> None:
    fh.write("reports/v.txt", "first")
    fh.write("reports/v.txt", "second")
    assert (repo_root / "reports" / "v.txt").read_text() == "second\n"
    assert not (repo_root / "reports" / "v.txt.tmp").exists()


# ---------------------------------------------------------------------------
# repo-source: syntax check + ID anchor injection
# ---------------------------------------------------------------------------


def test_repo_source_py_injects_id_anchor(fh: FileHandler, repo_root: Path) -> None:
    """A new public def in src/foo.py gets a # ID: anchor."""
    fh.write("src/foo.py", "def hello():\n    return 1\n")
    written = (repo_root / "src" / "foo.py").read_text()
    assert any(line.strip().startswith("# ID:") for line in written.splitlines())


def test_repo_source_py_invalid_syntax_raises(
    fh: FileHandler, repo_root: Path
) -> None:
    """Syntax-invalid .py under repo-source raises; file not written."""
    with pytest.raises(ValueError, match="Syntax Error"):
        fh.write("src/bad.py", "def broken(:\n")
    assert not (repo_root / "src" / "bad.py").exists()


def test_repo_source_private_defs_no_anchor(
    fh: FileHandler, repo_root: Path
) -> None:
    """Private symbols still skip ID anchor injection."""
    fh.write("src/foo.py", "def _helper():\n    return 1\n")
    written = (repo_root / "src" / "foo.py").read_text()
    assert not any(line.strip().startswith("# ID:") for line in written.splitlines())


# ---------------------------------------------------------------------------
# tests/ also classifies as repo-source (per ADR-097 D2)
# ---------------------------------------------------------------------------


def test_tests_path_injects_id_anchor(fh: FileHandler, repo_root: Path) -> None:
    """tests/ is repo-source — syntax check + ID anchor fire same as src/."""
    fh.write("tests/test_foo.py", "def test_hello():\n    assert True\n")
    written = (repo_root / "tests" / "test_foo.py").read_text()
    assert any(line.strip().startswith("# ID:") for line in written.splitlines())


# ---------------------------------------------------------------------------
# ephemeral-scratch: no source-shape transforms (the bug fix)
# ---------------------------------------------------------------------------


def test_ephemeral_scratch_no_id_anchor_injection(
    fh: FileHandler, repo_root: Path
) -> None:
    """var/tmp/.../src/foo.py classifies as ephemeral-scratch → NO ID anchors.
    This is the substring-bug fix ADR-097 D2 names: previously a path
    containing 'src/' as a sub-segment would get anchors injected
    mid-flight, corrupting crate materialization."""
    fh.write(
        "var/tmp/sandbox_xxx/src/bar.py",
        "def hello():\n    return 1\n",
    )
    written = (repo_root / "var" / "tmp" / "sandbox_xxx" / "src" / "bar.py").read_text()
    assert not any(line.strip().startswith("# ID:") for line in written.splitlines())


def test_ephemeral_scratch_skips_syntax_gate(
    fh: FileHandler, repo_root: Path
) -> None:
    """Syntax-invalid .py under var/tmp/ writes WITHOUT raising.
    ADR-097 D3: ephemeral tier has no schema/syntax gates."""
    fh.write("var/tmp/scratch/bad.py", "def broken(:\n")
    written = (repo_root / "var" / "tmp" / "scratch" / "bad.py").read_text()
    assert "def broken(:" in written


def test_ephemeral_scratch_trailing_newline_still_added(
    fh: FileHandler, repo_root: Path
) -> None:
    """Text writes still get trailing newline normalization regardless of class."""
    fh.write("var/tmp/scratch/note.txt", "hi")
    assert (repo_root / "var" / "tmp" / "scratch" / "note.txt").read_text() == "hi\n"


# ---------------------------------------------------------------------------
# runtime-output: no source-shape transforms
# ---------------------------------------------------------------------------


def test_runtime_output_no_id_anchor(fh: FileHandler, repo_root: Path) -> None:
    """reports/ is runtime-output — no source-shape transforms."""
    fh.write("reports/script.py", "def hello():\n    return 1\n")
    written = (repo_root / "reports" / "script.py").read_text()
    assert not any(line.strip().startswith("# ID:") for line in written.splitlines())


def test_runtime_output_trailing_newline_added(
    fh: FileHandler, repo_root: Path
) -> None:
    fh.write("reports/note.txt", "no newline")
    assert (repo_root / "reports" / "note.txt").read_text() == "no newline\n"


# ---------------------------------------------------------------------------
# Bytes path: no transforms regardless of target class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/blob.py",            # would be repo-source if str
        "reports/blob.bin",       # runtime-output
        "var/tmp/scratch.bin",    # ephemeral-scratch
    ],
)
def test_bytes_writes_exact_bytes_no_transforms(
    fh: FileHandler, repo_root: Path, rel_path: str
) -> None:
    """Bytes content writes exact bytes regardless of target class.
    No trailing-newline normalization, no syntax check, no ID anchors."""
    payload = b"def broken(: \xff\xfe"
    fh.write(rel_path, payload)
    assert (repo_root / rel_path).read_bytes() == payload


# ---------------------------------------------------------------------------
# Empty content
# ---------------------------------------------------------------------------


def test_empty_text_writes_single_newline(fh: FileHandler, repo_root: Path) -> None:
    """ensure_trailing_newline('') → '\\n'."""
    fh.write("reports/empty.txt", "")
    assert (repo_root / "reports" / "empty.txt").read_text() == "\n"


def test_empty_bytes_writes_zero_bytes(fh: FileHandler, repo_root: Path) -> None:
    fh.write("reports/empty.bin", b"")
    assert (repo_root / "reports" / "empty.bin").read_bytes() == b""
