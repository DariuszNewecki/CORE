"""Regression matrix pinning FileHandler post-guard behavior.

This suite locks down current observable behavior of FileHandler's
public mutation methods across the target-class taxonomy named in
ADR-097 D2. It is the verification baseline for the dispatch-flip
step of ADR-097 (Migration step 4) — any behavior change relative
to these tests is a regression and must be intentional.

Coverage axes:
- Methods: write_runtime_text/_bytes/_json, add_pending_write,
  ensure_dir, remove_file, remove_tree, copy_tree.
  copy_repo_snapshot is intentionally not exercised here — it
  requires a snapshottable repo shape that would dominate this
  matrix; its behavior is downstream of shutil.copytree which is
  well-pinned by Python's own tests. ADR-097 step 6 retired
  write_validated_bytes — its semantics fold into the unified
  `write` channel under repo-source-tier idempotent re-validation,
  so this matrix no longer pins a bypass cell.
- Target classes: repo-source (src/, tests/), runtime-output
  (reports/, var/cache/), ephemeral-scratch (var/tmp/), and
  governed-artifact (.intent/, .specs/) where reachable post-guard.
  The IntentGuard interaction is stubbed — this suite pins
  post-guard behavior only; guard semantics belong in the
  IntentGuard regression suite.

Known load-bearing quirk pinned here:
- _ensure_id_anchors used to trigger on substring 'src/' in rel_path,
  not on resolved target class — so a write to var/tmp/.../src/foo.py
  got ID anchors injected mid-flight. ADR-097 D2 names this the
  substring bug; step 4 removed it. The post-flip behavior is pinned
  here as test_substring_bug_pins_current_id_anchor_behavior so a
  regression that re-introduces substring-based dispatch is detected
  by a deliberate flip of that one assertion.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from body.infrastructure.storage.file_handler import FileHandler, FileOpResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _repo_var_tmp() -> Path:
    """Locate the repo's var/tmp/ for sanctioned ephemeral test writes.

    CLAUDE.md temp-file discipline: tests use var/tmp/ under the repo
    root, not the system temp dir. The path-walk is anchored at this
    test file's location and resolved up to the repo root.
    """
    here = Path(__file__).resolve()
    # tests/shared/test_file_handler__regression_matrix.py
    #   parents[0] = tests/shared/
    #   parents[1] = tests/
    #   parents[2] = <repo root>
    repo_root = here.parents[2]
    var_tmp = repo_root / "var" / "tmp"
    var_tmp.mkdir(parents=True, exist_ok=True)
    return var_tmp


@pytest.fixture
def repo_root() -> Path:
    """Create an ephemeral repo root under <repo>/var/tmp/ for one test.

    pytest's default tmp_path lives under the system tmp dir, which
    CLAUDE.md prohibits. We explicitly mkdtemp into var/tmp/ so every
    test write is sanctioned and the daemon's own var/tmp/ sweep can
    GC leaked dirs.
    """
    d = Path(tempfile.mkdtemp(prefix="fh_regression_", dir=str(_repo_var_tmp())))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fh(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> FileHandler:
    """FileHandler instance with IntentGuard interaction stubbed.

    The regression matrix pins post-guard behavior. Guard semantics
    (ADR-079 stage 1+) belong in the IntentGuard test suite. Stubbing
    _guard_paths to a no-op lets each test exercise the write/delete
    path independently of the guard's current advisory/blocking state.
    """
    handler = FileHandler(str(repo_root))
    monkeypatch.setattr(handler, "_guard_paths", lambda *a, **kw: None)
    return handler


# ---------------------------------------------------------------------------
# write_runtime_text — content transforms + return shape
# ---------------------------------------------------------------------------


def test_write_runtime_text_returns_success_filopresult(
    fh: FileHandler, repo_root: Path
) -> None:
    """Return shape: FileOpResult(status='success', message=..., detail=rel_path)."""
    result = fh.write_runtime_text("reports/note.txt", "hello")
    assert isinstance(result, FileOpResult)
    assert result.status == "success"
    assert result.message == "Wrote runtime text"
    assert result.detail == "reports/note.txt"


def test_write_runtime_text_appends_trailing_newline_when_absent(
    fh: FileHandler, repo_root: Path
) -> None:
    """Content lacking '\\n' gains exactly one — pins ensure_trailing_newline."""
    fh.write_runtime_text("reports/a.txt", "no newline")
    assert (repo_root / "reports" / "a.txt").read_text(
        encoding="utf-8"
    ) == "no newline\n"


def test_write_runtime_text_collapses_multiple_trailing_newlines(
    fh: FileHandler, repo_root: Path
) -> None:
    """ensure_trailing_newline rstrips '\\n' then appends one — n becomes 1."""
    fh.write_runtime_text("reports/b.txt", "x\n\n\n")
    assert (repo_root / "reports" / "b.txt").read_text(encoding="utf-8") == "x\n"


def test_write_runtime_text_empty_content_writes_single_newline(
    fh: FileHandler, repo_root: Path
) -> None:
    """Empty input becomes '\\n' on disk."""
    fh.write_runtime_text("reports/empty.txt", "")
    assert (repo_root / "reports" / "empty.txt").read_text(encoding="utf-8") == "\n"


def test_write_runtime_text_creates_parent_directories(
    fh: FileHandler, repo_root: Path
) -> None:
    """_atomic_write_text mkdir(parents=True) — nested target works."""
    fh.write_runtime_text("reports/audit/2026/x.json", '{"k":1}')
    assert (repo_root / "reports" / "audit" / "2026" / "x.json").exists()


def test_write_runtime_text_overwrites_existing_atomically(
    fh: FileHandler, repo_root: Path
) -> None:
    """Re-writing the same path replaces atomically; no .tmp suffix lingers."""
    fh.write_runtime_text("reports/v.txt", "first")
    fh.write_runtime_text("reports/v.txt", "second")
    target = repo_root / "reports" / "v.txt"
    assert target.read_text(encoding="utf-8") == "second\n"
    assert not (repo_root / "reports" / "v.txt.tmp").exists()


def test_write_runtime_text_strips_dot_slash_prefix(
    fh: FileHandler, repo_root: Path
) -> None:
    """'./foo' → 'foo' (per _resolve_repo_path docstring)."""
    fh.write_runtime_text("./reports/p.txt", "x")
    assert (repo_root / "reports" / "p.txt").exists()


# ---------------------------------------------------------------------------
# write_runtime_text — .py syntax gate
# ---------------------------------------------------------------------------


def test_write_runtime_text_py_valid_syntax_passes(
    fh: FileHandler, repo_root: Path
) -> None:
    """ast.parse-able .py content writes successfully."""
    fh.write_runtime_text("tests/test_x.py", "x = 1\n")
    assert (repo_root / "tests" / "test_x.py").exists()


def test_write_runtime_text_py_invalid_syntax_raises(
    fh: FileHandler, repo_root: Path
) -> None:
    """ast.parse failure raises ValueError; file is not written."""
    with pytest.raises(ValueError, match="Syntax Error"):
        fh.write_runtime_text("tests/test_y.py", "def broken(:\n")
    assert not (repo_root / "tests" / "test_y.py").exists()


def test_write_runtime_text_non_py_skips_syntax_gate(
    fh: FileHandler, repo_root: Path
) -> None:
    """Non-.py files are not parsed; invalid Python content writes fine."""
    fh.write_runtime_text("reports/note.txt", "def broken(:")
    assert (repo_root / "reports" / "note.txt").read_text(
        encoding="utf-8"
    ) == "def broken(:\n"


# ---------------------------------------------------------------------------
# write_runtime_text — ID anchor injection (the substring bug)
# ---------------------------------------------------------------------------
#
# Today's behavior: _ensure_id_anchors fires when the substring 'src/'
# is in rel_path. Three observable cells:
# - 'src/...' → injects
# - 'tests/...' → does NOT inject (no 'src/' substring)
# - 'var/tmp/<nested>/src/...' → injects (substring match, semantically wrong)
#
# ADR-097 step 4 makes the trigger target-class-aware (only repo-source
# class injects). When that flip lands, the third test below must
# change its assertion deliberately — that flip IS the bug fix.


def test_id_anchor_injected_for_src_paths(fh: FileHandler, repo_root: Path) -> None:
    """Public def in src/ without preceding '# ID:' gets one injected."""
    fh.write_runtime_text(
        "src/foo.py",
        "def hello():\n    return 1\n",
    )
    written = (repo_root / "src" / "foo.py").read_text(encoding="utf-8")
    lines = written.splitlines()
    assert any(line.strip().startswith("# ID:") for line in lines), (
        f"Expected '# ID:' anchor in src/ write, got:\n{written}"
    )


def test_id_anchor_not_reinjected_when_present(
    fh: FileHandler, repo_root: Path
) -> None:
    """Existing '# ID:' on the previous line suppresses re-injection."""
    content = "# ID: 11111111-2222-3333-4444-555555555555\ndef hello():\n    return 1\n"
    fh.write_runtime_text("src/foo.py", content)
    written = (repo_root / "src" / "foo.py").read_text(encoding="utf-8")
    id_lines = [
        line for line in written.splitlines() if line.strip().startswith("# ID:")
    ]
    assert len(id_lines) == 1, f"Expected exactly one '# ID:' line, got:\n{written}"


def test_id_anchor_skipped_for_private_defs(fh: FileHandler, repo_root: Path) -> None:
    """Private symbols ('_name') do not receive auto-anchors."""
    fh.write_runtime_text(
        "src/foo.py",
        "def _helper():\n    return 1\n",
    )
    written = (repo_root / "src" / "foo.py").read_text(encoding="utf-8")
    assert not any(line.strip().startswith("# ID:") for line in written.splitlines())


def test_id_anchor_injected_for_tests_paths(fh: FileHandler, repo_root: Path) -> None:
    """tests/ paths now DO get ID anchors (ADR-097 step 4 behavior).

    Before the flip: tests/ paths did NOT receive ID anchor injection
    because the trigger was the substring 'src/' in rel_path. After the
    flip: tests/ classifies as repo-source per ADR-097 D2, which gets
    the full source-shape transform set including ID anchors. The ADR
    explicitly lists 'splitting tests/ from src/' as out of scope —
    both share the repo-source tier.
    """
    fh.write_runtime_text(
        "tests/test_foo.py",
        "def test_hello():\n    assert True\n",
    )
    written = (repo_root / "tests" / "test_foo.py").read_text(encoding="utf-8")
    assert any(line.strip().startswith("# ID:") for line in written.splitlines())


def test_substring_bug_fixed_no_id_anchor_under_var_tmp(
    fh: FileHandler, repo_root: Path
) -> None:
    """The substring bug ADR-097 D2 named is now structurally fixed.

    A path under var/tmp/ that contains 'src/' as a sub-segment
    (e.g., shadow_materializer's crate-overlaid src/) classifies as
    ephemeral-scratch via the target_class_boundaries.yaml ordering
    (var/tmp/ matched before src/). The ephemeral-scratch tier in
    FileHandler.write skips source-shape transforms — no syntax
    check, no ID anchor injection — so the crate content materializes
    verbatim.

    Pre-ADR-097-step-4 behavior pinned by the earlier vintage of this
    test: 'has_anchor=True' (the bug). The flip from True → False is
    the load-bearing observable.
    """
    fh.write_runtime_text(
        "var/tmp/sandbox_xxx/src/bar.py",
        "def hello():\n    return 1\n",
    )
    written = (repo_root / "var" / "tmp" / "sandbox_xxx" / "src" / "bar.py").read_text(
        encoding="utf-8"
    )
    has_anchor = any(line.strip().startswith("# ID:") for line in written.splitlines())
    assert not has_anchor, (
        "Substring bug regression: ID anchor was injected for an "
        "ephemeral-scratch path. The target-class dispatch (ADR-097 step 4) "
        "should have classified var/tmp/.../src/... as ephemeral-scratch "
        "and skipped the source-shape transforms."
    )


# ---------------------------------------------------------------------------
# write_runtime_bytes — no transforms
# ---------------------------------------------------------------------------


def test_write_runtime_bytes_writes_exact_bytes(
    fh: FileHandler, repo_root: Path
) -> None:
    """Bytes path performs no trailing-newline normalization."""
    fh.write_runtime_bytes("reports/blob.bin", b"\x00\x01\x02")
    assert (repo_root / "reports" / "blob.bin").read_bytes() == b"\x00\x01\x02"


def test_write_runtime_bytes_skips_syntax_gate(
    fh: FileHandler, repo_root: Path
) -> None:
    """Even with .py extension, bytes path does not ast.parse."""
    fh.write_runtime_bytes("src/raw.py", b"def broken(:")
    assert (repo_root / "src" / "raw.py").read_bytes() == b"def broken(:"


def test_write_runtime_bytes_returns_success(fh: FileHandler, repo_root: Path) -> None:
    """Return shape: 'Wrote runtime bytes' / rel_path."""
    result = fh.write_runtime_bytes("reports/b.bin", b"x")
    assert result == FileOpResult("success", "Wrote runtime bytes", "reports/b.bin")


# ---------------------------------------------------------------------------
# write_runtime_json — payload serialization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload, expected_substring",
    [
        ({"a": 1, "b": [2, 3]}, '"a": 1'),
        ([1, 2, 3], "[\n  1,\n  2,\n  3\n]"),
        ("just-a-string", '"just-a-string"'),
        (42, "42"),
    ],
)
def test_write_runtime_json_serializes_payload_with_indent_2(
    fh: FileHandler,
    repo_root: Path,
    payload: Any,
    expected_substring: str,
) -> None:
    """JSON is written with json.dumps(payload, indent=2)."""
    fh.write_runtime_json("reports/x.json", payload)
    written = (repo_root / "reports" / "x.json").read_text(encoding="utf-8")
    assert expected_substring in written
    # Round-trip parse confirms structural validity:
    assert json.loads(written) == payload


def test_write_runtime_json_appends_trailing_newline(
    fh: FileHandler, repo_root: Path
) -> None:
    """After ADR-097 step 4, write_runtime_json delegates through the
    unified ``write`` entry, which applies ``ensure_trailing_newline``
    on the text path. The JSON output gains exactly one trailing
    ``\\n``.

    Pre-flip behavior (pinned by the earlier vintage of this test):
    ``write_runtime_json`` called ``_atomic_write_text`` directly with
    ``json.dumps(...)`` output, which ends mid-brace without a newline.
    The flip from False → True on the trailing-newline assertion is an
    expected ADR-097 step 4 observable: POSIX-friendly, diff-minimal,
    consistent with every other text write through FileHandler.
    """
    fh.write_runtime_json("reports/y.json", {"k": 1})
    written = (repo_root / "reports" / "y.json").read_text(encoding="utf-8")
    assert written.endswith("\n"), (
        "Post-ADR-097-step-4 regression: write_runtime_json should now "
        "append a trailing newline via the unified write entry."
    )


# ---------------------------------------------------------------------------
# add_pending_write — staging area writes
# ---------------------------------------------------------------------------


def test_add_pending_write_creates_pw_file_in_pending_dir(
    fh: FileHandler, repo_root: Path
) -> None:
    """Pending writes land under var/workflows/pending_writes/pw-<hash>.json."""
    path_str = fh.add_pending_write("test prompt", "src/new.py", "code body")
    out = Path(path_str)
    assert out.parent == repo_root / "var" / "workflows" / "pending_writes"
    assert out.name.startswith("pw-")
    assert out.name.endswith(".json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == {
        "prompt": "test prompt",
        "suggested_path": "src/new.py",
        "code": "code body",
    }


# ---------------------------------------------------------------------------
# ensure_dir — directory create
# ---------------------------------------------------------------------------


def test_ensure_dir_creates_nested_path(fh: FileHandler, repo_root: Path) -> None:
    """Multi-level dirs created in one call (mkdir parents=True)."""
    result = fh.ensure_dir("reports/audit/2026")
    assert result.status == "success"
    assert (repo_root / "reports" / "audit" / "2026").is_dir()


def test_ensure_dir_idempotent_when_exists(fh: FileHandler, repo_root: Path) -> None:
    """Calling twice does not error (mkdir exist_ok=True)."""
    fh.ensure_dir("reports/x")
    result = fh.ensure_dir("reports/x")
    assert result.status == "success"
    assert (repo_root / "reports" / "x").is_dir()


def test_ensure_dir_strips_trailing_slash(fh: FileHandler, repo_root: Path) -> None:
    """'reports/x/' is equivalent to 'reports/x'."""
    fh.ensure_dir("reports/x/")
    assert (repo_root / "reports" / "x").is_dir()


# ---------------------------------------------------------------------------
# remove_file / remove_tree
# ---------------------------------------------------------------------------


def test_remove_file_deletes_existing(fh: FileHandler, repo_root: Path) -> None:
    target = repo_root / "reports" / "to_del.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x", encoding="utf-8")
    result = fh.remove_file("reports/to_del.txt")
    assert result.status == "success"
    assert not target.exists()


def test_remove_file_missing_ok_on_absent(fh: FileHandler, repo_root: Path) -> None:
    """No error if target doesn't exist (Path.unlink(missing_ok=True))."""
    result = fh.remove_file("reports/never_existed.txt")
    assert result.status == "success"


def test_remove_tree_deletes_directory(fh: FileHandler, repo_root: Path) -> None:
    target = repo_root / "reports" / "tree_to_del"
    (target / "a" / "b").mkdir(parents=True)
    (target / "f.txt").write_text("x", encoding="utf-8")
    result = fh.remove_tree("reports/tree_to_del")
    assert result.status == "success"
    assert not target.exists()


def test_remove_tree_ignore_errors_on_absent(fh: FileHandler, repo_root: Path) -> None:
    """shutil.rmtree(ignore_errors=True) — absent target is a no-op."""
    result = fh.remove_tree("reports/no_such_tree")
    assert result.status == "success"


# ---------------------------------------------------------------------------
# copy_tree
# ---------------------------------------------------------------------------


def test_copy_tree_replicates_structure(fh: FileHandler, repo_root: Path) -> None:
    src = repo_root / "reports" / "src_tree"
    (src / "a").mkdir(parents=True)
    (src / "a" / "x.txt").write_text("hello", encoding="utf-8")
    result = fh.copy_tree("reports/src_tree", "reports/dst_tree")
    assert result.status == "success"
    assert (repo_root / "reports" / "dst_tree" / "a" / "x.txt").read_text(
        encoding="utf-8"
    ) == "hello"


def test_copy_tree_replaces_existing_destination(
    fh: FileHandler, repo_root: Path
) -> None:
    """Pre-existing destination is wiped before copy."""
    src = repo_root / "src_tree"
    (src).mkdir()
    (src / "new.txt").write_text("new", encoding="utf-8")
    dst = repo_root / "dst_tree"
    (dst).mkdir()
    (dst / "stale.txt").write_text("stale", encoding="utf-8")

    fh.copy_tree("src_tree", "dst_tree")
    assert (dst / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (dst / "stale.txt").exists()


# ---------------------------------------------------------------------------
# _resolve_repo_path — path escape protection
# ---------------------------------------------------------------------------


def test_resolve_repo_path_rejects_parent_escape(
    fh: FileHandler, repo_root: Path
) -> None:
    """'../evil' resolves outside repo and is rejected."""
    with pytest.raises(ValueError, match="escape repository boundary"):
        fh._resolve_repo_path("../evil")


def test_resolve_repo_path_preserves_intent_prefix(
    fh: FileHandler, repo_root: Path
) -> None:
    """'.intent/foo' must NOT be coerced to 'intent/foo' by leading-dot
    stripping — the leading dot must survive so IntentGuard's tier-1
    invariant on .intent/ writes can trigger.

    Per the _resolve_repo_path docstring: removeprefix('./') is used
    rather than lstrip('./') for exactly this reason.
    """
    resolved = fh._resolve_repo_path(".intent/foo.yaml")
    # The resolved path must be under <repo>/.intent/, not <repo>/intent/.
    assert resolved.is_relative_to(repo_root / ".intent")


def test_resolve_repo_path_strips_dot_slash_prefix(
    fh: FileHandler, repo_root: Path
) -> None:
    """'./foo' → '<repo>/foo' (removeprefix strips './' once)."""
    resolved = fh._resolve_repo_path("./foo.txt")
    assert resolved == repo_root / "foo.txt"
