# tests/shared/infrastructure/test_git_service_demo_clone.py
"""Unit tests for GitService's ADR-155 disposable-clone + marker-checked-cleanup
primitives.

Covers Phase 1 test-plan U04, U05, U06 (see the companion Phase1-Map): no
dangerous git calls against the invoking repo anywhere in the new demo
modules, clone isolation (copied objects, no remote, pinned HEAD), and the
marker-checked-removal guard's refusal cases — the highest-value Phase 1
test per the map.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

import cli.logic.demo.isolation as isolation_module
from shared.infrastructure.git_service import DEMO_RUN_MARKER_FILENAME, GitService


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def source_repo(tmp_path: Path) -> GitService:
    """Real, throwaway git repo with one commit — fresh per test."""
    repo_dir = tmp_path / "source"
    repo_dir.mkdir()
    _run(["git", "init"], repo_dir)
    _run(["git", "config", "user.email", "demo@test.local"], repo_dir)
    _run(["git", "config", "user.name", "Demo Test"], repo_dir)
    _run(["git", "config", "commit.gpgsign", "false"], repo_dir)
    (repo_dir / "README.md").write_text("hello\n")
    _run(["git", "add", "README.md"], repo_dir)
    _run(["git", "commit", "-m", "initial"], repo_dir)
    return GitService(repo_dir)


@pytest.fixture
def demo_state_root(tmp_path: Path) -> Path:
    root = tmp_path / "demo_state"
    root.mkdir()
    return root


def _make_valid_run_dir(state_root: Path, run_id: str) -> Path:
    run_dir = state_root / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / DEMO_RUN_MARKER_FILENAME).write_text(run_id, encoding="utf-8")
    return run_dir


def _find_any_loose_object(objects_dir: Path) -> Path:
    for sub in sorted(objects_dir.iterdir()):
        if sub.is_dir() and len(sub.name) == 2:
            for obj in sub.iterdir():
                if obj.is_file():
                    return obj
    raise AssertionError(f"no loose git object found under {objects_dir}")


# --- U04: no dangerous git calls against the invoking repo in demo code ---


def test_u04_isolation_module_has_no_invoking_repo_mutation_calls() -> None:
    source = inspect.getsource(isolation_module).lower()
    assert "reset --hard" not in source
    assert "git clean" not in source
    assert "checkout ." not in source
    assert "restore ." not in source


# --- U05: clone uses copied objects, no remote, pinned HEAD ---


def test_u05_disposable_clone_has_copied_objects(
    source_repo: GitService, tmp_path: Path
) -> None:
    head = source_repo.get_current_commit()
    dest = tmp_path / "clone"
    clone = source_repo.create_disposable_clone(head, dest)

    source_obj = _find_any_loose_object(source_repo.repo_path / ".git" / "objects")
    rel = source_obj.relative_to(source_repo.repo_path / ".git" / "objects")
    clone_obj = clone.repo_path / ".git" / "objects" / rel

    assert clone_obj.exists()
    assert clone_obj.stat().st_ino != source_obj.stat().st_ino
    assert clone_obj.stat().st_nlink == 1


def test_u05_disposable_clone_has_no_remote_and_pinned_head(
    source_repo: GitService, tmp_path: Path
) -> None:
    head = source_repo.get_current_commit()
    clone = source_repo.create_disposable_clone(head, tmp_path / "clone")

    assert clone.get_current_commit() == head
    assert clone.clone_has_no_remote() is True


# --- U06: marker_checked_remove refusal cases (highest-value Phase 1 test) ---


def test_marker_checked_remove_succeeds_on_a_legitimate_run_dir(
    demo_state_root: Path,
) -> None:
    run_id = "run-abc"
    run_dir = _make_valid_run_dir(demo_state_root, run_id)
    GitService.marker_checked_remove(run_dir, run_id, demo_state_root)
    assert not run_dir.exists()


def test_u06_refuses_wrong_parent(demo_state_root: Path, tmp_path: Path) -> None:
    run_id = "run-wrongparent"
    wrong_dir = tmp_path / "elsewhere" / run_id
    wrong_dir.mkdir(parents=True)
    (wrong_dir / DEMO_RUN_MARKER_FILENAME).write_text(run_id, encoding="utf-8")

    with pytest.raises(ValueError, match="does not match the expected run directory"):
        GitService.marker_checked_remove(wrong_dir, run_id, demo_state_root)
    assert wrong_dir.exists()


def test_u06_refuses_missing_marker(demo_state_root: Path) -> None:
    run_id = "run-nomark"
    run_dir = demo_state_root / "runs" / run_id
    run_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="missing marker file"):
        GitService.marker_checked_remove(run_dir, run_id, demo_state_root)
    assert run_dir.exists()


def test_u06_refuses_marker_mismatch(demo_state_root: Path) -> None:
    run_id = "run-mismatch"
    run_dir = demo_state_root / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / DEMO_RUN_MARKER_FILENAME).write_text("some-other-run-id", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match run_id"):
        GitService.marker_checked_remove(run_dir, run_id, demo_state_root)
    assert run_dir.exists()


def test_u06_refuses_symlink_escape(demo_state_root: Path, tmp_path: Path) -> None:
    run_id = "run-symlink"
    real_target = tmp_path / "outside_target"
    real_target.mkdir()
    (real_target / "canary.txt").write_text("do not delete me\n")
    run_dir = demo_state_root / "runs" / run_id
    run_dir.parent.mkdir(parents=True)
    run_dir.symlink_to(real_target, target_is_directory=True)

    with pytest.raises(ValueError, match="is a symlink"):
        GitService.marker_checked_remove(run_dir, run_id, demo_state_root)
    assert real_target.exists()
    assert (real_target / "canary.txt").exists()


def test_u06_refuses_root_target(demo_state_root: Path) -> None:
    with pytest.raises(ValueError, match="does not match the expected run directory"):
        GitService.marker_checked_remove(Path("/"), "anything", demo_state_root)


def test_u06_refuses_source_repo_path(
    demo_state_root: Path, source_repo: GitService
) -> None:
    run_id = "run-source"
    with pytest.raises(ValueError, match="does not match the expected run directory"):
        GitService.marker_checked_remove(source_repo.repo_path, run_id, demo_state_root)
    assert source_repo.repo_path.exists()


def test_u06_refuses_unsafe_run_id_characters(demo_state_root: Path) -> None:
    with pytest.raises(ValueError, match="unsafe character"):
        GitService.marker_checked_remove(
            demo_state_root / "runs" / "x", "../$HOME", demo_state_root
        )


# --- marker_checked_resolve: validate-only half used by `demo cleanup` dry-run ---


# ID: d303b849-8be3-4705-a8ad-256d1289f6aa
def test_marker_checked_resolve_returns_target_without_removing(
    demo_state_root: Path,
) -> None:
    run_id = "run-resolve-ok"
    run_dir = _make_valid_run_dir(demo_state_root, run_id)
    resolved = GitService.marker_checked_resolve(run_dir, run_id, demo_state_root)
    assert resolved == run_dir.resolve()
    # Validation only — nothing removed.
    assert run_dir.exists()
    assert (run_dir / DEMO_RUN_MARKER_FILENAME).exists()


# ID: dec29458-85f2-404a-aa74-ca3f2c23be95
def test_marker_checked_resolve_applies_the_same_guards(demo_state_root: Path) -> None:
    run_id = "run-resolve-nomark"
    run_dir = demo_state_root / "runs" / run_id
    run_dir.mkdir(parents=True)
    with pytest.raises(ValueError, match="missing marker file"):
        GitService.marker_checked_resolve(run_dir, run_id, demo_state_root)
    assert run_dir.exists()


# --- Fingerprint support methods (used by capture_fingerprint) ---


def test_write_tree_and_list_files(source_repo: GitService) -> None:
    tree_sha = source_repo.write_tree()
    assert len(tree_sha) == 40
    assert source_repo.list_tracked_files() == ["README.md"]
    assert source_repo.list_untracked_files() == []

    (source_repo.repo_path / "scratch.txt").write_text("untracked\n")
    assert source_repo.list_untracked_files() == ["scratch.txt"]
