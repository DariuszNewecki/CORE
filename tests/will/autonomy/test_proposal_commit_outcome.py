"""commit_proposal_changes returns a typed CommitOutcome (ADR-148 D3).

The crux: a failed (non-contamination) git commit must NOT complete the
proposal. It returns CommitOutcome.FAILED so the executor routes to
mark_failed + rollback rather than leaving a completed row with no git
record — superseding the ADR-129 D7 clause that returned success on
non-contamination git errors.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from shared.infrastructure.git_service import GitService, StagingContaminationError
from will.autonomy.proposal_execution_pipeline import (
    CommitOutcome,
    commit_proposal_changes,
)


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "target.py").write_text("# original\n", encoding="utf-8")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return tmp_path


_PRODUCED = {"fix.format:0": {"ok": True, "data": {"_sandbox_target_paths": ["target.py"]}}}


# ID: 41ba428f-cab9-4add-b2dd-c2698d6e87ec
def test_commit_outcome_committed_on_real_commit(repo: Path) -> None:
    (repo / "target.py").write_text("# action-produced\n", encoding="utf-8")
    outcome = commit_proposal_changes(
        git_service=GitService(repo),
        proposal_id="p-committed",
        proposal_goal="fix.format",
        action_results=_PRODUCED,
    )
    assert outcome is CommitOutcome.COMMITTED


# ID: 445d306d-e9bf-4f26-b3ab-f5252bffcae8
def test_commit_outcome_nothing_to_commit_on_empty_production(repo: Path) -> None:
    outcome = commit_proposal_changes(
        git_service=GitService(repo),
        proposal_id="p-empty",
        proposal_goal="fix.format",
        action_results={"fix.format:0": {"ok": True, "data": {"_sandbox_target_paths": []}}},
    )
    assert outcome is CommitOutcome.NOTHING_TO_COMMIT


# ID: 0314bef6-5fec-4467-a893-c8672c8d8215
def test_commit_outcome_nothing_to_commit_when_no_git_service() -> None:
    outcome = commit_proposal_changes(
        git_service=None,
        proposal_id="p-nogit",
        proposal_goal="fix.format",
        action_results=_PRODUCED,
    )
    assert outcome is CommitOutcome.NOTHING_TO_COMMIT


# ID: 7987a6e6-b709-42ae-bcb4-38312550cc98
def test_commit_outcome_failed_on_git_error() -> None:
    # ADR-148 D3: a non-contamination git failure must NOT complete the proposal.
    git = MagicMock()
    git.commit_paths.side_effect = RuntimeError("pre-commit hook exploded")
    outcome = commit_proposal_changes(
        git_service=git,
        proposal_id="p-failed",
        proposal_goal="fix.format",
        action_results=_PRODUCED,
    )
    assert outcome is CommitOutcome.FAILED


# ID: 43e23e01-f017-4eda-be73-76261e2fa1e0
def test_commit_outcome_refused_on_staging_contamination() -> None:
    git = MagicMock()
    git.commit_paths.side_effect = StagingContaminationError("staged work outside production set")
    outcome = commit_proposal_changes(
        git_service=git,
        proposal_id="p-contam",
        proposal_goal="fix.format",
        action_results=_PRODUCED,
    )
    assert outcome is CommitOutcome.REFUSED_CONTAMINATION
