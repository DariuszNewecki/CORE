"""Tests for shared.infrastructure.external_target_binding (Unit A, EC-1A).

Governor ruling 2026-09-05 (ADR-159 Notes): bounded pre-experiment safety
package, read-only evaluation before any controlled-write evaluation.

Real disposable git repositories under pytest's tmp_path are used
throughout; git/filesystem behavior is never mocked. Mocks/subprocess
isolation are used only for the two IntentRepository-non-initialization
tests, where a genuine behavioral check requires either inspecting the
real module-global singleton state or spawning a fresh interpreter.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from shared.infrastructure.external_target_binding import (
    ExternalTargetBindingError,
    validate_external_target_binding,
)


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def _init_repo(path: Path, *, with_intent: bool = True) -> Path:
    """Create a real, committed git repository at *path*."""
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], path)
    _run(["git", "config", "user.email", "test@external-binding.local"], path)
    _run(["git", "config", "user.name", "External Binding Test"], path)
    _run(["git", "config", "commit.gpgsign", "false"], path)
    if with_intent:
        (path / ".intent").mkdir(parents=True, exist_ok=True)
        (path / ".intent" / "marker.txt").write_text("marker\n")
    (path / "README.md").write_text("test repo\n")
    _run(["git", "add", "-A"], path)
    _run(["git", "commit", "-m", "initial"], path)
    return path


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    return _init_repo(tmp_path / "target", with_intent=True)


@pytest.fixture
def core_root(tmp_path: Path) -> Path:
    return _init_repo(tmp_path / "core", with_intent=True)


def _valid_kwargs(target: Path, core_root_path: Path) -> dict:
    return {
        "repo_path_value": str(target),
        "mind_value": str(target / ".intent"),
        "database_url_value": "postgresql+asyncpg://user:pw@localhost/experiment_db",
        "core_repo_root": core_root_path,
    }


class TestValidBindingSucceeds:
    def test_valid_external_repository_binding_succeeds(self, target_repo, core_root):
        result = validate_external_target_binding(
            target_repo, **_valid_kwargs(target_repo, core_root)
        )
        assert result == target_repo.resolve()

    def test_ordinary_git_directory_succeeds(self, target_repo, core_root):
        assert (target_repo / ".git").is_dir()
        validate_external_target_binding(
            target_repo, **_valid_kwargs(target_repo, core_root)
        )

    def test_worktree_style_git_file_is_accepted(
        self, target_repo, core_root, tmp_path
    ):
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=target_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        worktree_path = tmp_path / "worktree-target"
        _run(
            ["git", "worktree", "add", "--detach", str(worktree_path), sha],
            target_repo,
        )
        try:
            assert (worktree_path / ".git").is_file()
            result = validate_external_target_binding(
                worktree_path, **_valid_kwargs(worktree_path, core_root)
            )
            assert result == worktree_path.resolve()
        finally:
            _run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                target_repo,
            )

    def test_symlinked_target_resolves_transparently_and_succeeds(
        self, tmp_path, core_root
    ):
        real_outside = _init_repo(tmp_path / "real_outside", with_intent=True)
        symlink_target = tmp_path / "symlink_target"
        symlink_target.symlink_to(real_outside, target_is_directory=True)
        result = validate_external_target_binding(
            symlink_target,
            repo_path_value=str(symlink_target),
            mind_value=str(symlink_target / ".intent"),
            database_url_value="postgresql+asyncpg://u:p@localhost/db",
            core_repo_root=core_root,
        )
        assert result == real_outside.resolve()

    def test_does_not_create_or_modify_files(self, target_repo, core_root):
        before = sorted(p.relative_to(target_repo) for p in target_repo.rglob("*"))
        validate_external_target_binding(
            target_repo, **_valid_kwargs(target_repo, core_root)
        )
        after = sorted(p.relative_to(target_repo) for p in target_repo.rglob("*"))
        assert before == after


class TestRefusals:
    def test_missing_target_refuses(self, tmp_path, core_root):
        missing = tmp_path / "does-not-exist"
        with pytest.raises(ExternalTargetBindingError):
            validate_external_target_binding(
                missing, **_valid_kwargs(missing, core_root)
            )

    def test_non_directory_target_refuses(self, tmp_path, core_root):
        file_target = tmp_path / "just_a_file"
        file_target.write_text("not a repo\n")
        with pytest.raises(ExternalTargetBindingError):
            validate_external_target_binding(
                file_target, **_valid_kwargs(file_target, core_root)
            )

    def test_missing_git_refuses(self, tmp_path, core_root):
        no_git = tmp_path / "no_git"
        no_git.mkdir()
        (no_git / ".intent").mkdir()
        with pytest.raises(ExternalTargetBindingError, match=r"\.git"):
            validate_external_target_binding(no_git, **_valid_kwargs(no_git, core_root))

    def test_subdirectory_of_another_repo_refuses(self, target_repo, core_root):
        """Realistic shape: a plain subdirectory of an existing repo with no
        .git of its own -- the common way an operator could mistakenly point
        at 'a subdirectory inside another repository.'"""
        subdir = target_repo / "nested"
        subdir.mkdir()
        (subdir / ".intent").mkdir()
        with pytest.raises(ExternalTargetBindingError):
            validate_external_target_binding(subdir, **_valid_kwargs(subdir, core_root))

    def test_missing_intent_refuses(self, tmp_path, core_root):
        no_intent = _init_repo(tmp_path / "no_intent", with_intent=False)
        with pytest.raises(ExternalTargetBindingError, match=r"\.intent"):
            validate_external_target_binding(
                no_intent, **_valid_kwargs(no_intent, core_root)
            )
        assert not (no_intent / ".intent").exists()

    def test_absent_repo_path_refuses(self, target_repo, core_root):
        kwargs = _valid_kwargs(target_repo, core_root)
        kwargs["repo_path_value"] = None
        with pytest.raises(ExternalTargetBindingError, match="REPO_PATH"):
            validate_external_target_binding(target_repo, **kwargs)

    def test_mismatched_repo_path_refuses(self, target_repo, core_root, tmp_path):
        other = _init_repo(tmp_path / "other", with_intent=True)
        kwargs = _valid_kwargs(target_repo, core_root)
        kwargs["repo_path_value"] = str(other)
        with pytest.raises(ExternalTargetBindingError, match="REPO_PATH"):
            validate_external_target_binding(target_repo, **kwargs)

    def test_absent_mind_refuses(self, target_repo, core_root):
        kwargs = _valid_kwargs(target_repo, core_root)
        kwargs["mind_value"] = None
        with pytest.raises(ExternalTargetBindingError, match="MIND"):
            validate_external_target_binding(target_repo, **kwargs)

    def test_mismatched_mind_refuses(self, target_repo, core_root, tmp_path):
        other = _init_repo(tmp_path / "other2", with_intent=True)
        kwargs = _valid_kwargs(target_repo, core_root)
        kwargs["mind_value"] = str(other / ".intent")
        with pytest.raises(ExternalTargetBindingError, match="MIND"):
            validate_external_target_binding(target_repo, **kwargs)

    def test_absent_database_url_refuses(self, target_repo, core_root):
        kwargs = _valid_kwargs(target_repo, core_root)
        kwargs["database_url_value"] = None
        with pytest.raises(ExternalTargetBindingError, match="DATABASE_URL"):
            validate_external_target_binding(target_repo, **kwargs)

    def test_empty_database_url_refuses(self, target_repo, core_root):
        kwargs = _valid_kwargs(target_repo, core_root)
        kwargs["database_url_value"] = ""
        with pytest.raises(ExternalTargetBindingError, match="DATABASE_URL"):
            validate_external_target_binding(target_repo, **kwargs)

    def test_core_own_root_refuses(self, core_root):
        with pytest.raises(ExternalTargetBindingError, match="CORE"):
            validate_external_target_binding(
                core_root, **_valid_kwargs(core_root, core_root)
            )

    def test_nested_beneath_core_root_refuses(self, core_root):
        nested = _init_repo(core_root / "nested_target", with_intent=True)
        with pytest.raises(ExternalTargetBindingError, match="beneath CORE"):
            validate_external_target_binding(nested, **_valid_kwargs(nested, core_root))

    def test_symlink_escape_into_core_root_refuses_safely(self, tmp_path, core_root):
        """A path that textually looks unrelated to CORE's root, but whose
        symlink resolves inside it, must be refused -- proving comparisons
        use the canonical (resolved) path, not the raw operator-supplied
        text."""
        real_dest = _init_repo(core_root / "nested_via_symlink", with_intent=True)
        sneaky_link = tmp_path / "looks_external"
        sneaky_link.symlink_to(real_dest, target_is_directory=True)
        with pytest.raises(ExternalTargetBindingError, match="beneath CORE"):
            validate_external_target_binding(
                sneaky_link,
                repo_path_value=str(sneaky_link),
                mind_value=str(sneaky_link / ".intent"),
                database_url_value="postgresql+asyncpg://u:p@localhost/db",
                core_repo_root=core_root,
            )

    def test_refusal_never_includes_database_credentials(self, target_repo, core_root):
        secret_url = "postgresql+asyncpg://admin:SuperSecret123@localhost/experiment_db"
        kwargs = _valid_kwargs(target_repo, core_root)
        kwargs["repo_path_value"] = None  # force a refusal unrelated to DATABASE_URL
        kwargs["database_url_value"] = secret_url
        with pytest.raises(ExternalTargetBindingError) as excinfo:
            validate_external_target_binding(target_repo, **kwargs)
        assert "SuperSecret123" not in str(excinfo.value)
        assert secret_url not in str(excinfo.value)


class TestIntentRepositoryIsolation:
    def test_invoking_guard_does_not_touch_intent_repository_singleton(
        self, target_repo, core_root
    ):
        from shared.infrastructure.intent import intent_repository as intent_repo_module

        before = intent_repo_module._INTENT_REPO

        validate_external_target_binding(
            target_repo, **_valid_kwargs(target_repo, core_root)
        )
        assert intent_repo_module._INTENT_REPO is before

        kwargs = _valid_kwargs(target_repo, core_root)
        kwargs["database_url_value"] = None
        with pytest.raises(ExternalTargetBindingError):
            validate_external_target_binding(target_repo, **kwargs)
        assert intent_repo_module._INTENT_REPO is before

    def test_importing_guard_module_does_not_initialize_intent_repository_singleton(
        self,
    ):
        """Isolated-subprocess check: a fresh interpreter that imports only
        the guard module (and never calls it) must leave the
        IntentRepository *singleton* uninitialized.

        Note: the ``intent_repository`` *module* may already be present in
        ``sys.modules`` before this guard is ever touched — unrelated
        pre-existing ``shared/`` machinery (``shared/__init__.py``'s eager
        imports -> ``shared.component_primitive``'s plugin-discovery
        helpers) transitively imports it regardless of this module. Module
        presence is not the property that matters; the guard's own contract
        (module docstring) is specifically that it never *initializes or
        rebinds* the singleton — i.e. never calls ``get_intent_repository()``
        — which is what this test verifies directly.
        """
        src_root = Path(__file__).resolve().parents[3] / "src"
        script = (
            "import shared.infrastructure.external_target_binding\n"
            "from shared.infrastructure.intent import intent_repository as m\n"
            "print('SINGLETON_IS_NONE=' + str(m._INTENT_REPO is None))\n"
        )
        env = {**os.environ, "PYTHONPATH": str(src_root)}
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "SINGLETON_IS_NONE=True" in result.stdout
