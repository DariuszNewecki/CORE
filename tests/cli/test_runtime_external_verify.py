"""Tests for cli.runtime_external_verify (Unit B launcher,
Governor-authorized external-target safety package; Governor ruling
2026-09-05).

Verification only -- these tests must never trigger a proposal, action,
or worker execution, and must never mutate the external test repository.

Most tests call :func:`run` directly, in-process, for speed. A few
properties -- "fails before importing heavy runtime modules" -- can only
be proven with a genuinely fresh interpreter (other tests in this same
session will already have imported ``body.infrastructure.bootstrap``),
so those use a real subprocess invocation of ``python -m cli.admin_cli``,
mirroring Unit A's own isolated-subprocess precedent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cli.runtime_external_verify import (
    _RECURSION_GUARD_ENV,
    EXIT_BINDING_REFUSED,
    EXIT_INTERNAL_FAILURE,
    EXIT_VERIFIED,
    find_root_disagreements,
    matches_route,
    run,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MACHINERY_FLOOR = REPO_ROOT / "src" / "shared" / "_machinery_floor"

VALID_DATABASE_URL = (
    "postgresql+asyncpg://opuser:s3cr3t-pw@localhost:5432/experiment_db"
)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _build_external_repo(path: Path) -> Path:
    """A disposable, real git repo with the minimum valid machinery floor
    copied from CORE's own bundled reference (``shared/_machinery_floor``)
    -- test setup only, distinct from the later committed ``package/``
    mutation fixture."""
    path.mkdir(parents=True, exist_ok=True)
    _git(["init"], path)
    _git(["config", "user.email", "test@external-verify.local"], path)
    _git(["config", "user.name", "External Verify Test"], path)
    _git(["config", "commit.gpgsign", "false"], path)
    shutil.copytree(
        MACHINERY_FLOOR,
        path / ".intent",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (path / "README.md").write_text("external verify test repo\n")
    _git(["add", "-A"], path)
    _git(["commit", "-m", "initial"], path)
    return path


@pytest.fixture
def external_repo(tmp_path: Path) -> Path:
    return _build_external_repo(tmp_path / "target")


def _argv(target: Path) -> list[str]:
    return ["runtime", "external-verify", "--target", str(target)]


def _run_cli_subprocess(
    args: list[str], env_overrides: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Invoke `python -m cli.admin_cli <args>` in a genuinely fresh
    interpreter, so import-order guarantees can be checked without
    interference from whatever this pytest session has already
    imported."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), **env_overrides}
    return subprocess.run(
        [sys.executable, "-m", "cli.admin_cli", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestMatchesRoute:
    def test_exact_route_matches(self):
        assert matches_route(["runtime", "external-verify", "--target", "x"])
        assert matches_route(["runtime", "external-verify"])

    def test_unrelated_argv_does_not_match(self):
        assert not matches_route([])
        assert not matches_route(["runtime"])
        assert not matches_route(["code", "audit"])
        assert not matches_route(["runtime", "health"])
        assert not matches_route(["--help"])


class TestRefusals:
    def test_absent_database_url_refuses(self, external_repo, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        result = run(_argv(external_repo))
        assert result == EXIT_BINDING_REFUSED

    def test_core_own_root_refuses(self, monkeypatch, capsys):
        monkeypatch.setenv("DATABASE_URL", VALID_DATABASE_URL)
        result = run(_argv(REPO_ROOT))
        captured = capsys.readouterr()
        assert result == EXIT_BINDING_REFUSED
        assert "CORE" in captured.err

    def test_recursion_protection(self, external_repo, monkeypatch, capsys):
        monkeypatch.setenv(_RECURSION_GUARD_ENV, "1")
        monkeypatch.setenv("DATABASE_URL", VALID_DATABASE_URL)
        result = run(_argv(external_repo))
        captured = capsys.readouterr()
        assert result == EXIT_BINDING_REFUSED
        assert "recursive" in captured.err.lower()

    def test_credentials_never_leak_on_refusal(self, monkeypatch, capsys, tmp_path):
        secret_url = "postgresql+asyncpg://admin:TopSecret999@localhost/db"
        monkeypatch.setenv("DATABASE_URL", secret_url)
        missing = tmp_path / "does-not-exist"
        result = run(_argv(missing))
        captured = capsys.readouterr()
        assert result == EXIT_BINDING_REFUSED
        assert "TopSecret999" not in captured.out
        assert "TopSecret999" not in captured.err


class TestRootAgreement:
    def test_find_root_disagreements_reports_none_when_all_agree(self, tmp_path):
        target = tmp_path / "t"
        mind = target / ".intent"
        disagreements = find_root_disagreements(
            git_service_repo_path=target,
            settings_repo_path=target,
            settings_mind=mind,
            bootstrap_registry_repo_path=target,
            service_registry_repo_path=target,
            intent_repository_root=mind,
            expected_target=target,
            expected_mind=mind,
        )
        assert disagreements == []

    def test_find_root_disagreements_reports_the_specific_mismatch(self, tmp_path):
        target = tmp_path / "t"
        mind = target / ".intent"
        wrong = tmp_path / "wrong"
        disagreements = find_root_disagreements(
            git_service_repo_path=target,
            settings_repo_path=target,
            settings_mind=mind,
            bootstrap_registry_repo_path=wrong,  # deliberate mismatch
            service_registry_repo_path=target,
            intent_repository_root=mind,
            expected_target=target,
            expected_mind=mind,
        )
        assert len(disagreements) == 1
        assert disagreements[0].startswith("BootstrapRegistry.get_repo_path()=")

    def test_disagreement_after_bootstrap_refuses(
        self, external_repo, monkeypatch, capsys
    ):
        """Integration proof that run() itself refuses on a real
        post-construction disagreement. Monkeypatching BootstrapRegistry's
        public accessor is the one deliberate, narrowly-scoped mock in
        this suite: forcing a genuine disagreement without it would mean
        contriving an actual infrastructure bug.

        Note: in this shared pytest session, ``shared.config``'s
        ``settings`` singleton is typically already constructed (bound to
        CORE's own root) by an earlier-loaded fixture elsewhere in the
        suite, so other roots may *also* independently disagree here.
        That does not weaken this test: the monkeypatch guarantees a
        specific, deliberate ``BootstrapRegistry`` mismatch is present and
        reported, which is what this assertion checks for."""
        monkeypatch.setenv("DATABASE_URL", VALID_DATABASE_URL)

        from shared.infrastructure.bootstrap_registry import bootstrap_registry

        wrong_path = external_repo.parent  # anything != external_repo
        monkeypatch.setattr(bootstrap_registry, "get_repo_path", lambda: wrong_path)

        result = run(_argv(external_repo))
        captured = capsys.readouterr()

        assert result == EXIT_INTERNAL_FAILURE
        assert "disagree" in captured.err.lower()
        assert "BootstrapRegistry" in captured.err


class TestSubprocessImportOrdering:
    """Properties that can only be proven with a genuinely fresh
    interpreter (other tests in this session will already have imported
    body.infrastructure.bootstrap)."""

    def test_invalid_target_fails_before_heavy_runtime_import(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        result = _run_cli_subprocess(
            _argv(missing), {"DATABASE_URL": VALID_DATABASE_URL}
        )
        assert result.returncode == EXIT_BINDING_REFUSED
        assert "registered successfully" not in result.stdout
        assert "registered successfully" not in result.stderr
        assert "REFUSED" in result.stdout or "REFUSED" in result.stderr

    def test_missing_intent_fails_before_bootstrap(self, tmp_path):
        no_intent = tmp_path / "no_intent"
        no_intent.mkdir()
        _git(["init"], no_intent)
        _git(["config", "user.email", "t@t.local"], no_intent)
        _git(["config", "user.name", "T"], no_intent)
        _git(["config", "commit.gpgsign", "false"], no_intent)
        (no_intent / "f.txt").write_text("x\n")
        _git(["add", "-A"], no_intent)
        _git(["commit", "-m", "initial"], no_intent)

        result = _run_cli_subprocess(
            _argv(no_intent), {"DATABASE_URL": VALID_DATABASE_URL}
        )
        assert result.returncode == EXIT_BINDING_REFUSED
        assert "registered successfully" not in result.stdout
        assert "registered successfully" not in result.stderr

    def test_valid_verification_succeeds_end_to_end(self, external_repo):
        result = _run_cli_subprocess(
            _argv(external_repo), {"DATABASE_URL": VALID_DATABASE_URL}
        )
        assert result.returncode == EXIT_VERIFIED
        assert "VERIFIED — no mutation executed" in result.stdout
        assert str(external_repo.resolve()) in result.stdout
        assert "s3cr3t-pw" not in result.stdout
        assert "s3cr3t-pw" not in result.stderr

    def test_environment_binding_wins_over_ambient_contamination(
        self, external_repo, tmp_path
    ):
        """Prove REPO_PATH/MIND are bound to the *target*, not left as
        whatever the ambient (wrong) environment already had, before
        Settings() is ever constructed. Requires a fresh interpreter: an
        in-process test cannot observe this because shared.config's
        Settings() singleton is a once-per-process object."""
        wrong = tmp_path / "not-the-target"
        wrong.mkdir()
        result = _run_cli_subprocess(
            _argv(external_repo),
            {
                "DATABASE_URL": VALID_DATABASE_URL,
                "REPO_PATH": str(wrong),
                "MIND": str(wrong / ".intent"),
            },
        )
        assert result.returncode == EXIT_VERIFIED
        assert str(external_repo.resolve()) in result.stdout
        assert str(wrong) not in result.stdout

    def test_no_database_connection_attempted(self, external_repo):
        """An unreachable DATABASE_URL host must not stall or fail the
        run — CoreContext wires a session factory, it never opens a
        session, so no connection is ever attempted."""
        result = _run_cli_subprocess(
            _argv(external_repo),
            {
                "DATABASE_URL": (
                    "postgresql+asyncpg://u:p@nonexistent-host-xyz.invalid:5432/db"
                )
            },
        )
        assert result.returncode == EXIT_VERIFIED

    def test_does_not_modify_target_worktree_or_history(self, external_repo):
        def _snapshot() -> tuple[str, str, str]:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=external_repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            tree = subprocess.run(
                ["git", "write-tree"],
                cwd=external_repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=external_repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            return head, tree, status

        before = _snapshot()
        result = _run_cli_subprocess(
            _argv(external_repo), {"DATABASE_URL": VALID_DATABASE_URL}
        )
        after = _snapshot()

        assert result.returncode == EXIT_VERIFIED
        assert before == after

    def test_help_still_works(self):
        result = _run_cli_subprocess(["--help"], {})
        assert result.returncode == 0
        assert "core-admin" in result.stdout or "Usage" in result.stdout

    def test_representative_existing_command_still_dispatches(self):
        result = _run_cli_subprocess(["code", "--help"], {})
        assert result.returncode == 0
        assert "audit" in result.stdout
