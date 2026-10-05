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
    assert post_sha == pre_sha, "ADR-101 D2: empty production set must emit no commit"
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
    assert proposal_id[:16] in msg, "commit message must carry the proposal_id prefix"


def test_proposal_commit_carries_cores_identity_not_the_accounts(
    repo_with_target: Path,
) -> None:
    """#951 / ADR-101 D1: CORE produced the bytes, so the commit's author
    AND committer are CORE's identity -- not the account's git identity
    (here the repo-local "Test <test@example.com>", standing in for the
    daemon account's global identity, which is a person's)."""
    (repo_with_target / "target.py").write_text("# action bytes\n")
    commit_proposal_changes(
        git_service=GitService(repo_with_target),
        proposal_id="951-identity-proposal",
        proposal_goal="fix.format",
        action_results=_production("target.py"),
    )
    who = _run(["git", "log", "-1", "--format=%an <%ae>|%cn <%ce>"], repo_with_target)
    assert who == (
        "CORE daemon <core-daemon@core.invalid>|CORE daemon <core-daemon@core.invalid>"
    )


def test_commit_paths_without_identity_keeps_the_process_identity(
    repo_with_target: Path,
) -> None:
    """Human-invoked commits (dev integrate, refactor CLI) are unchanged."""
    (repo_with_target / "target.py").write_text("# operator bytes\n")
    GitService(repo_with_target).commit_paths(["target.py"], "operator change")
    who = _run(["git", "log", "-1", "--format=%an <%ae>"], repo_with_target)
    assert who == "Test <test@example.com>"


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


def _status(repo: Path, *paths: str) -> str:
    return _run(["git", "status", "--porcelain", "--", *paths], repo)


def _production(*paths: str) -> dict:
    return {"fix.x:0": {"ok": True, "data": {"_sandbox_target_paths": list(paths)}}}


def test_rollback_reverts_an_already_staged_mutation(tmp_path: Path) -> None:
    """#871: the mutation was ``git add``-ed (commit_paths' staging step)
    before the commit failed. Rollback must restore index AND working tree
    to the baseline; an unrelated staged path stays staged."""
    repo = tmp_path
    _init_repo(repo)
    (repo / "target.py").write_text("baseline\n")
    (repo / "other.py").write_text("other\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "initial"], repo)
    pre_sha = _run(["git", "rev-parse", "HEAD"], repo)

    (repo / "target.py").write_text("staged mutation\n")
    (repo / "other.py").write_text("operator staged edit\n")
    _run(["git", "add", "target.py", "other.py"], repo)

    problem = rollback_proposal(
        git_service=GitService(repo),
        proposal_id="test-871",
        action_results=_production("target.py"),
        pre_sha=pre_sha,
    )

    assert problem is None
    assert (repo / "target.py").read_text() == "baseline\n"
    assert _status(repo, "target.py") == "", "index and worktree back at baseline"
    assert _status(repo, "other.py") == "M  other.py", "unrelated staged edit kept"


def test_rollback_removes_files_the_action_created(tmp_path: Path) -> None:
    """A path absent from the baseline was produced by the action: staged
    or untracked, it is removed. Unrelated untracked files stay."""
    repo = tmp_path
    _init_repo(repo)
    (repo / "keep.py").write_text("k\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "initial"], repo)
    pre_sha = _run(["git", "rev-parse", "HEAD"], repo)

    (repo / "pkg").mkdir()
    (repo / "pkg/new_staged.py").write_text("x\n")
    (repo / "pkg/new_untracked.py").write_text("y\n")
    (repo / "operator_scratch.txt").write_text("mine\n")
    _run(["git", "add", "pkg/new_staged.py"], repo)

    problem = rollback_proposal(
        git_service=GitService(repo),
        proposal_id="test-871-created",
        action_results=_production("pkg/new_staged.py", "pkg/new_untracked.py"),
        pre_sha=pre_sha,
    )

    assert problem is None
    assert not (repo / "pkg/new_staged.py").exists()
    assert not (repo / "pkg/new_untracked.py").exists()
    assert _status(repo, "pkg") == ""
    assert (repo / "operator_scratch.txt").read_text() == "mine\n"


def test_rollback_restores_to_the_baseline_not_a_later_head(tmp_path: Path) -> None:
    """The restoration source is the captured pre-execution SHA."""
    repo = tmp_path
    _init_repo(repo)
    (repo / "t.py").write_text("v1\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "v1"], repo)
    pre_sha = _run(["git", "rev-parse", "HEAD"], repo)
    (repo / "t.py").write_text("v2\n")
    _run(["git", "commit", "-qam", "v2"], repo)

    problem = rollback_proposal(
        git_service=GitService(repo),
        proposal_id="test-871-source",
        action_results=_production("t.py"),
        pre_sha=pre_sha,
    )

    assert problem is None
    assert (repo / "t.py").read_text() == "v1\n"


def test_rollback_without_a_baseline_is_reported_not_silent() -> None:
    problem = rollback_proposal(
        git_service=object(),
        proposal_id="test-871-nobase",
        action_results=_production("a.py"),
        pre_sha=None,
    )
    assert problem is not None
    assert "no pre-execution baseline" in problem
    assert "a.py" in problem


def test_rollback_residue_is_reported() -> None:
    class _Git:
        def restore_paths(self, paths, source):
            return ["a.py"]

    problem = rollback_proposal(
        git_service=_Git(),
        proposal_id="test-871-residue",
        action_results=_production("a.py"),
        pre_sha="f" * 40,
    )
    assert problem is not None
    assert "still differ" in problem and "a.py" in problem


def test_rollback_error_is_reported_not_swallowed() -> None:
    class _Git:
        def restore_paths(self, paths, source):
            raise RuntimeError("Git command failed: index.lock exists")

    problem = rollback_proposal(
        git_service=_Git(),
        proposal_id="test-871-raise",
        action_results=_production("a.py"),
        pre_sha="f" * 40,
    )
    assert problem is not None
    assert "index.lock" in problem


def test_nothing_to_roll_back_is_not_a_problem(tmp_path: Path) -> None:
    assert (
        rollback_proposal(
            git_service=object(),
            proposal_id="test-871-empty",
            action_results=_production(),
            pre_sha="f" * 40,
        )
        is None
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


def test_post_execution_sha_is_always_branch_reachable(
    repo_with_target: Path,
) -> None:
    """#658 ask #1: the sha recorded as ``post_execution_sha`` is structurally
    always reachable from a branch — there is no window that orphans a commit.

    ProposalExecutor records ``post_execution_sha = git rev-parse HEAD`` of the
    MAIN repo, captured *after* ``commit_proposal_changes`` (proposal_executor
    .py:336-361). ``commit_proposal_changes`` commits the production set on the
    main branch (advancing HEAD) and is fail-soft. So whether a commit is
    emitted (HEAD = new commit) or not (HEAD = prior commit), the captured HEAD
    is reachable from a branch — the exact invariant CommitReachabilityAuditor
    checks. The pre-ADR-106 orphans came from recording a *sandbox-worktree*
    commit that went unreachable after teardown; this pins that the current
    path records main HEAD only.
    """
    git_service = GitService(repo_with_target)

    # Case 1 — non-empty production: a commit is emitted, HEAD advances.
    (repo_with_target / "target.py").write_text("# action-produced reformatting\n")
    commit_proposal_changes(
        git_service=git_service,
        proposal_id="reach-nonempty",
        proposal_goal="fix.format",
        action_results={
            "fix.format:0": {
                "ok": True,
                "data": {"_sandbox_target_paths": ["target.py"]},
            }
        },
    )
    post_sha = git_service.get_current_commit()
    assert _run(["git", "branch", "--contains", post_sha], repo_with_target).strip(), (
        "post_execution_sha (HEAD after commit) must be branch-reachable — no orphan"
    )

    # Case 2 — empty production: fail-soft, no commit; the HEAD that would be
    # recorded is the prior commit, which is likewise reachable.
    pre = git_service.get_current_commit()
    commit_proposal_changes(
        git_service=git_service,
        proposal_id="reach-empty",
        proposal_goal="fix.format",
        action_results={
            "fix.format:0": {"ok": True, "data": {"_sandbox_target_paths": []}}
        },
    )
    post_sha_2 = git_service.get_current_commit()
    assert post_sha_2 == pre, "empty production must emit no commit (ADR-101 D2)"
    assert _run(
        ["git", "branch", "--contains", post_sha_2], repo_with_target
    ).strip(), "the no-commit path still records a branch-reachable HEAD — no orphan"
