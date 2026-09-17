# tests/body/infrastructure/storage/test_file_handler__repository_containment.py

"""architecture.execution_write.repository_containment -- G2 fixtures.

passive_gate, attestation class A: the enforcement IS FileHandler's refusal
at the single write chokepoint (ADR-097 D2). The violating fixture proves a
real outside-root write is refused before mutation, with the typed error
carrying rule_id / attempted_path / bound_root and remaining a ValueError
for existing catchers. The compliant fixture proves a valid inside-root
write lands. Real writes under var/tmp/; IntentGuard stubbed as in
test_file_handler__regression_matrix.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from body.infrastructure.storage.file_handler import FileHandler
from shared.exceptions import RepositoryBoundaryViolationError


RULE_ID = "architecture.execution_write.repository_containment"


@pytest.fixture
def repo_root() -> Path:
    var_tmp = Path(__file__).resolve().parents[3] / "var" / "tmp"
    var_tmp.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="fh_containment_", dir=str(var_tmp)))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fh(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> FileHandler:
    handler = FileHandler(str(repo_root))
    monkeypatch.setattr(handler, "_guard_paths", lambda *a, **kw: None)
    return handler


def test_outside_root_write_is_refused_with_rule_id(
    fh: FileHandler, repo_root: Path
) -> None:
    # A sibling of the bound root, reached both by traversal and absolutely.
    outside = repo_root.parent / f"{repo_root.name}_outside_probe.py"
    assert not outside.exists()
    try:
        for target in (f"../{outside.name}", str(outside)):
            with pytest.raises(RepositoryBoundaryViolationError) as excinfo:
                fh.write_runtime_text(target, "x = 1\n")
            err = excinfo.value
            assert isinstance(err, ValueError)  # existing catchers unchanged
            assert err.rule_id == RULE_ID
            assert err.attempted_path == target
            assert err.bound_root == str(repo_root.resolve())
            payload = err.to_payload()
            assert payload["rule_id"] == RULE_ID
            assert "escape repository boundary" in payload["message"]
        # refused BEFORE mutation: nothing was written anywhere
        assert not outside.exists()
        assert list(repo_root.rglob("*.py")) == []
    finally:
        outside.unlink(missing_ok=True)


def test_inside_root_write_succeeds(fh: FileHandler, repo_root: Path) -> None:
    result = fh.write_runtime_text("src/inside.py", "x = 1\n")
    assert result.status == "success"
    assert (repo_root / "src" / "inside.py").read_text(encoding="utf-8") == "x = 1\n"


def test_legacy_value_error_catcher_still_matches(
    fh: FileHandler, repo_root: Path
) -> None:
    """The pre-existing regression-matrix contract (pytest.raises(ValueError,
    match='escape repository boundary')) is preserved by the typed error."""
    with pytest.raises(ValueError, match="escape repository boundary"):
        fh.write_runtime_text("../escape.py", "x = 1\n")


# --- #908: directory helpers must not re-root absolute paths -----------------
#
# ensure_dir / remove_tree / copy_tree / copy_repo_snapshot used to
# ``.strip("/")`` their argument BEFORE _resolve_repo_path, so an absolute
# path lost its leading slash and was joined to the root as if relative:
# ensure_dir("/opt/dev/CORE/var/x") created <root>/opt/dev/CORE/var/x and an
# outside-root absolute path (/etc/x) became <root>/etc/x -- accepted instead
# of refused by rule. Both directions are pinned here.


def test_ensure_dir_absolute_inside_root_resolves_in_place(
    fh: FileHandler, repo_root: Path
) -> None:
    target = repo_root / "var" / "reports" / "decisions"
    result = fh.ensure_dir(str(target))
    assert result.status == "success"
    assert target.is_dir()
    # not re-rooted: no <root>/<root-as-relative>/... phantom tree
    phantom = repo_root / str(target).lstrip("/")
    assert not phantom.exists()
    assert result.detail == "var/reports/decisions"


def test_ensure_dir_absolute_outside_root_is_refused_with_rule_id(
    fh: FileHandler, repo_root: Path
) -> None:
    outside = repo_root.parent / f"{repo_root.name}_outside_dir_probe"
    assert not outside.exists()
    try:
        with pytest.raises(RepositoryBoundaryViolationError) as excinfo:
            fh.ensure_dir(str(outside))
        err = excinfo.value
        assert err.rule_id == RULE_ID
        assert err.attempted_path == str(outside)
        assert err.bound_root == str(repo_root.resolve())
        # refused BEFORE mutation: neither the real target nor a re-rooted copy
        assert not outside.exists()
        assert not (repo_root / str(outside).lstrip("/")).exists()
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def test_remove_tree_absolute_outside_root_is_refused(
    fh: FileHandler, repo_root: Path
) -> None:
    outside = repo_root.parent / f"{repo_root.name}_outside_rm_probe"
    outside.mkdir()
    try:
        with pytest.raises(RepositoryBoundaryViolationError):
            fh.remove_tree(str(outside))
        assert outside.is_dir()  # untouched
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def test_copy_tree_absolute_inside_root_resolves_in_place(
    fh: FileHandler, repo_root: Path
) -> None:
    src = repo_root / "var" / "a"
    src.mkdir(parents=True)
    (src / "f.txt").write_text("x\n", encoding="utf-8")
    dst = repo_root / "var" / "b"
    result = fh.copy_tree(str(src), str(dst))
    assert result.status == "success"
    assert (dst / "f.txt").read_text(encoding="utf-8") == "x\n"
    assert not (repo_root / str(dst).lstrip("/")).exists()


def test_copy_repo_snapshot_absolute_outside_root_is_refused(
    fh: FileHandler, repo_root: Path
) -> None:
    outside = repo_root.parent / f"{repo_root.name}_outside_snap_probe"
    try:
        with pytest.raises(RepositoryBoundaryViolationError):
            fh.copy_repo_snapshot(str(outside))
        assert not outside.exists()
        assert not (repo_root / str(outside).lstrip("/")).exists()
    finally:
        shutil.rmtree(outside, ignore_errors=True)
