# tests/cli/logic/demo/test_isolation.py
"""Unit tests for the isolated consequence-chain demo's Phase 1 substrate
orchestration (ADR-155, ``cli.logic.demo.isolation``).

Covers Phase1-Map U13, U15 (partial), E02, E03 (partial), E04, E06, plus the
supporting run-identity/fingerprint/isolation-proof primitives. Compose
lifecycle tests requiring real Docker live in ``test_compose_lifecycle.py``.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from cli.logic.demo.isolation import (
    SubstrateTimeoutError,
    capture_fingerprint,
    cleanup_run,
    compose_up,
    create_isolated_clone,
    generate_run_identity,
    hash_directory,
    hash_file,
    prove_clone_isolation,
)
from shared.infrastructure.git_service import GitService
from shared.utils.subprocess_utils import SubprocessResult


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


# --- generate_run_identity ---


def test_generate_run_identity_writes_marker_matching_run_id(tmp_path: Path) -> None:
    identity = generate_run_identity(tmp_path / "state")
    assert identity.state_dir.exists()
    assert identity.marker_path.read_text(encoding="utf-8") == identity.run_id
    assert identity.state_dir == tmp_path / "state" / "runs" / identity.run_id
    assert identity.clone_dir == identity.state_dir / "clone"


def test_generate_run_identity_produces_unique_ids(tmp_path: Path) -> None:
    a = generate_run_identity(tmp_path / "state")
    b = generate_run_identity(tmp_path / "state")
    assert a.run_id != b.run_id
    assert a.state_dir != b.state_dir


# --- hash_file / hash_directory ---


def test_hash_file_is_deterministic_and_content_sensitive(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello\n")
    h1 = hash_file(f)
    assert hash_file(f) == h1
    f.write_text("hello!\n")
    assert hash_file(f) != h1


def test_u13_hash_directory_is_deterministic_and_detects_mutation(tmp_path: Path) -> None:
    d = tmp_path / "dir"
    (d / "sub").mkdir(parents=True)
    (d / "a.txt").write_text("a\n")
    (d / "sub" / "b.txt").write_text("b\n")

    h1 = hash_directory(d)
    assert hash_directory(d) == h1  # deterministic re-computation

    (d / "sub" / "b.txt").write_text("b-mutated\n")
    assert hash_directory(d) != h1  # mutation detected


# --- capture_fingerprint ---


def test_capture_fingerprint_reflects_tracked_and_untracked_content(
    source_repo: GitService,
) -> None:
    fp1 = capture_fingerprint(source_repo)
    assert fp1.head_sha == source_repo.get_current_commit()
    assert fp1.untracked_files == {}

    (source_repo.repo_path / "untracked.txt").write_text("u1\n")
    fp2 = capture_fingerprint(source_repo)
    assert fp2.untracked_files == {
        "untracked.txt": hash_file(source_repo.repo_path / "untracked.txt")
    }
    assert not fp1.matches(fp2)

    (source_repo.repo_path / "untracked.txt").write_text("u2\n")
    fp3 = capture_fingerprint(source_repo)
    assert fp3.head_sha == fp2.head_sha
    assert fp3.tracked_tree_sha == fp2.tracked_tree_sha
    assert fp3.untracked_files != fp2.untracked_files


# --- prove_clone_isolation ---


def test_prove_clone_isolation_passes_for_a_correct_clone(
    source_repo: GitService, tmp_path: Path
) -> None:
    head = source_repo.get_current_commit()
    identity = generate_run_identity(tmp_path / "state")
    clone = create_isolated_clone(source_repo, head, identity)
    prove_clone_isolation(clone, head)  # must not raise


def test_prove_clone_isolation_raises_if_remote_present(
    source_repo: GitService, tmp_path: Path
) -> None:
    head = source_repo.get_current_commit()
    identity = generate_run_identity(tmp_path / "state")
    clone = create_isolated_clone(source_repo, head, identity)
    _run(["git", "remote", "add", "origin", str(source_repo.repo_path)], clone.repo_path)

    with pytest.raises(ValueError, match="still has a remote"):
        prove_clone_isolation(clone, head)


def test_prove_clone_isolation_raises_on_head_mismatch(
    source_repo: GitService, tmp_path: Path
) -> None:
    head = source_repo.get_current_commit()
    identity = generate_run_identity(tmp_path / "state")
    clone = create_isolated_clone(source_repo, head, identity)

    with pytest.raises(ValueError, match="expected"):
        prove_clone_isolation(clone, "0" * 40)


# --- E02: dirty invoking repo untouched across clone + cleanup ---


def test_e02_dirty_invoking_repo_untouched_by_clone_and_cleanup(
    source_repo: GitService, tmp_path: Path
) -> None:
    # Seed pre-existing dirty state: unstaged, staged, and untracked.
    (source_repo.repo_path / "README.md").write_text("hello\nmodified unstaged\n")
    (source_repo.repo_path / "staged_new.txt").write_text("staged content\n")
    _run(["git", "add", "staged_new.txt"], source_repo.repo_path)
    (source_repo.repo_path / "untracked_new.txt").write_text("untracked content\n")

    before = capture_fingerprint(source_repo)
    head = source_repo.get_current_commit()
    demo_state_dir = tmp_path / "state"

    identity = generate_run_identity(demo_state_dir)
    clone = create_isolated_clone(source_repo, head, identity)
    prove_clone_isolation(clone, head)
    cleanup_run(identity, demo_state_dir)

    after = capture_fingerprint(source_repo)
    assert before.matches(after)
    assert not identity.state_dir.exists()


# --- E03 (partial): compose env is passed through verbatim, never merged with os.environ ---


class _FakeProcess:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"", b""


async def test_e03_compose_up_env_is_passed_through_verbatim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> _FakeProcess:
        captured["args"] = args
        captured["env"] = kwargs.get("env")
        return _FakeProcess()

    monkeypatch.setattr(
        "shared.utils.subprocess_utils.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setenv("DATABASE_URL", "postgres://sentinel-should-not-leak")

    explicit_env = {"COMPOSE_PROJECT_NAME": "run123"}
    await compose_up("run123", tmp_path / "compose.yaml", explicit_env)

    assert captured["env"] == explicit_env
    assert "sentinel-should-not-leak" not in str(captured["env"])


# --- E04: concurrent runs get distinct identities and independent cleanup ---


def test_e04_concurrent_runs_get_distinct_identities_and_independent_cleanup(
    source_repo: GitService, tmp_path: Path
) -> None:
    demo_state_dir = tmp_path / "state"
    head = source_repo.get_current_commit()

    identity_a = generate_run_identity(demo_state_dir)
    identity_b = generate_run_identity(demo_state_dir)
    assert identity_a.run_id != identity_b.run_id
    assert identity_a.state_dir != identity_b.state_dir

    create_isolated_clone(source_repo, head, identity_a)
    clone_b = create_isolated_clone(source_repo, head, identity_b)

    cleanup_run(identity_a, demo_state_dir)

    assert not identity_a.state_dir.exists()
    assert identity_b.state_dir.exists()
    assert clone_b.repo_path.exists()
    assert clone_b.get_current_commit() == head


# --- E06: failure immediately after clone, before any infra started ---


def test_e06_failure_after_clone_leaves_invoking_repo_unchanged_and_clone_removable(
    source_repo: GitService, tmp_path: Path
) -> None:
    before = capture_fingerprint(source_repo)
    head = source_repo.get_current_commit()
    demo_state_dir = tmp_path / "state"

    identity = generate_run_identity(demo_state_dir)
    clone = create_isolated_clone(source_repo, head, identity)
    prove_clone_isolation(clone, head)

    # Simulated failure here, before compose_up is ever called — no infra started.
    after = capture_fingerprint(source_repo)
    assert before.matches(after)

    cleanup_run(identity, demo_state_dir)
    assert not identity.state_dir.exists()


# --- U15 (partial): substrate waits carry a named, enforced deadline ---


async def test_u15_compose_up_raises_substrate_timeout_on_a_slow_wait(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def _slow_compose_command(*_args: object, **_kwargs: object) -> SubprocessResult:
        await asyncio.sleep(5)
        return SubprocessResult(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(
        "cli.logic.demo.isolation.run_compose_command", _slow_compose_command
    )

    with pytest.raises(SubstrateTimeoutError, match="compose up exceeded its"):
        await compose_up(
            "run-timeout", tmp_path / "compose.yaml", {}, timeout_seconds=0.05
        )


# --- E12 (partial): cancellation during compose_up doesn't corrupt cleanup ---
#
# Full E12 coverage (SIGINT -> process exit code 130) requires a CLI
# entrypoint that installs a signal handler and translates it to an exit
# code — that's Phase 3. This proves the substrate-level precondition: even
# if compose_up is cancelled mid-wait, the run's filesystem state is still
# in a condition cleanup_run can remove (bounded cleanup, no corruption).


async def test_e12_partial_cancellation_during_compose_up_leaves_cleanup_intact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def _hanging_compose_command(*_args: object, **_kwargs: object) -> SubprocessResult:
        await asyncio.sleep(30)
        return SubprocessResult(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(
        "cli.logic.demo.isolation.run_compose_command", _hanging_compose_command
    )

    demo_state_dir = tmp_path / "state"
    identity = generate_run_identity(demo_state_dir)

    task = asyncio.ensure_future(
        compose_up(identity.run_id, tmp_path / "compose.yaml", {})
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Cancellation must not have touched the run's filesystem state —
    # cleanup still succeeds cleanly afterward.
    cleanup_run(identity, demo_state_dir)
    assert not identity.state_dir.exists()
