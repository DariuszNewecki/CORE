"""ADR-101 D1 verification — commit authorship integrity.

Four integration-level regression tests covering the scenarios named in
ADR-101's Verification section. These were spec'd by the ADR but did
NOT ship with the implementation commit (f51d7c8d); the existing
test_proposal_executor_files_produced.py covers only compute_production_set
at the unit level. These tests close the spec-vs-shipped gap.

Coverage:
1. test_no_commit_when_production_empty_preserves_architect_bytes — the
   #594 / e7a591be regression shape. Empty production set + dirty
   architect tree → no commit emitted, architect bytes survive byte-for-byte.
2. test_commit_proposal_changes_attributes_only_action_bytes — the
   non-empty production happy path. Commit contains exactly the
   production-set diff; message attributes the action.
3. test_rollback_proposal_restores_only_action_touched_paths — D3
   rollback symmetry. Architect bytes on scope paths the action did not
   touch survive the rollback.
4. test_autonomy_dirty_tree_loader_retired and
   test_check_scope_collision_retired — D4 retirement of the pre-claim
   collision check and its dirty-tree YAML loader.

Tests exercise `commit_proposal_changes` / `rollback_proposal` directly
with synthesized action_results, avoiding the full ProposalExecutor DI
graph. The git repo fixture mirrors the pattern in
tests/body/atomic/test_executor_worktree_isolation.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.git_service import GitService
from will.autonomy.proposal_execution_pipeline import (
    commit_proposal_changes,
    rollback_proposal,
)


def _run(args: list[str], cwd: Path) -> str:
    res = subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)
    return res.stdout.strip()


def _init_repo(repo: Path) -> None:
    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)


@pytest.fixture
def repo_with_target(tmp_path: Path) -> Path:
    """Real git repo with target.py committed at initial SHA."""
    _init_repo(tmp_path)
    (tmp_path / "target.py").write_text("# original\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return tmp_path


def test_no_commit_when_production_empty_preserves_architect_bytes(
    repo_with_target: Path,
) -> None:
    """ADR-101 D2: idempotent action against already-correct input emits
    no commit. The architect's uncommitted edits to scope paths survive
    byte-for-byte — this is the #594 / e7a591be shape closed by construction.
    """
    architect_bytes = "# architect WIP — not yet committed\nimport os\n"
    (repo_with_target / "target.py").write_text(architect_bytes)
    pre_sha = _run(["git", "rev-parse", "HEAD"], repo_with_target)

    git_service = GitService(repo_with_target)
    action_results = {
        "fix.format:0": {
            "ok": True,
            "data": {"_sandbox_target_paths": []},
        }
    }

    commit_proposal_changes(
        git_service=git_service,
        proposal_id="test-empty-production",
        proposal_goal="fix.format",
        action_results=action_results,
    )

    post_sha = _run(["git", "rev-parse", "HEAD"], repo_with_target)
    assert post_sha == pre_sha, (
        "ADR-101 D2: empty production set must emit no commit"
    )
    assert (repo_with_target / "target.py").read_text() == architect_bytes, (
        "ADR-101 D1: architect's uncommitted bytes must survive byte-for-byte"
    )


def test_commit_proposal_changes_attributes_only_action_bytes(
    repo_with_target: Path,
) -> None:
    """ADR-101 D2 happy path: action produces a non-empty sandbox change
    (here the propagated bytes already sit in target.py in the working
    tree). commit_proposal_changes commits exactly the production set;
    the commit message attributes the action."""
    sandbox_bytes = "# action-produced reformatting\n"
    (repo_with_target / "target.py").write_text(sandbox_bytes)
    pre_sha = _run(["git", "rev-parse", "HEAD"], repo_with_target)

    git_service = GitService(repo_with_target)
    proposal_id = "6a084883-bbde-4066-test-happy-path"
    action_results = {
        "fix.format:0": {
            "ok": True,
            "data": {"_sandbox_target_paths": ["target.py"]},
        }
    }

    commit_proposal_changes(
        git_service=git_service,
        proposal_id=proposal_id,
        proposal_goal="fix.format",
        action_results=action_results,
    )

    post_sha = _run(["git", "rev-parse", "HEAD"], repo_with_target)
    assert post_sha != pre_sha, "non-empty production must produce a commit"

    diff_paths = _run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", post_sha],
        repo_with_target,
    ).split("\n")
    assert diff_paths == ["target.py"], (
        "commit diff must contain exactly the production-set paths"
    )

    msg = _run(["git", "log", "-1", "--format=%s"], repo_with_target)
    assert "fix.format" in msg, "commit message must name the action"
    assert proposal_id[:16] in msg, (
        "commit message must carry the proposal_id prefix"
    )


def test_rollback_proposal_restores_only_action_touched_paths(
    tmp_path: Path,
) -> None:
    """ADR-101 D3: rollback restores the production set, not scope.files.
    Architect uncommitted bytes on scope paths the action did NOT touch
    survive the rollback unchanged."""
    repo = tmp_path
    _init_repo(repo)
    (repo / "a.py").write_text("# a original\n")
    (repo / "b.py").write_text("# b original\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "initial"], repo)
    pre_sha = _run(["git", "rev-parse", "HEAD"], repo)

    (repo / "a.py").write_text("# action mutated a\n")
    architect_b_bytes = "# architect WIP on b\n"
    (repo / "b.py").write_text(architect_b_bytes)

    git_service = GitService(repo)
    action_results = {
        "fix.first:0": {
            "ok": True,
            "data": {"_sandbox_target_paths": ["a.py"]},
        }
    }

    rollback_proposal(
        git_service=git_service,
        proposal_id="test-rollback-symmetry",
        action_results=action_results,
        pre_sha=pre_sha,
    )

    assert (repo / "a.py").read_text() == "# a original\n", (
        "ADR-101 D3: rollback must restore the production-set path"
    )
    assert (repo / "b.py").read_text() == architect_b_bytes, (
        "ADR-101 D3: scope paths the action did NOT touch must retain "
        "architect's uncommitted bytes"
    )


def test_autonomy_dirty_tree_loader_retired() -> None:
    """ADR-101 D4: autonomy_dirty_tree.yaml + loader were retired
    alongside _check_scope_collision. The loader module no longer exists.
    """
    with pytest.raises(ModuleNotFoundError):
        import shared.infrastructure.intent.autonomy_dirty_tree  # noqa: F401


def test_check_scope_collision_retired() -> None:
    """ADR-101 D4: ProposalExecutor._check_scope_collision is removed.
    The pre-claim collision check contributed no remaining safety property
    once D2's production-set commit calculation landed."""
    from will.autonomy.proposal_executor import ProposalExecutor

    assert not hasattr(ProposalExecutor, "_check_scope_collision"), (
        "ADR-101 D4: _check_scope_collision must be retired"
    )
