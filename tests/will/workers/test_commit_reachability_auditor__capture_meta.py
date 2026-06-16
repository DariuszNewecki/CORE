"""Regression test for CommitReachabilityAuditor orphan-metadata capture (#658).

The 3 historical orphans (``211c2dd2`` / ``bbbb27fe`` / ``fca9a971``) were
resolvable only by manual git archaeology because the orphan finding carried
just the bare sha. ``_capture_commit_meta`` reads a *dangling* commit's
subject / author / date — ``git show -s`` resolves branch-unreachable objects
until ``git gc`` prunes them — so the orphan finding becomes self-describing
and the audit trail survives past the point the recorded sha would otherwise
point at nothing (ask #2 of #658).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from will.workers.commit_reachability_auditor import _capture_commit_meta


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)


@pytest.mark.asyncio
async def test_capture_meta_reads_dangling_commit(tmp_path: Path) -> None:
    """A branch-unreachable (dangling) commit's metadata is still captured —
    the exact orphan scenario the auditor must reconcile before GC."""
    _init_repo(tmp_path)
    (tmp_path / "f.py").write_text("# v1\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)

    # Second commit, then move the branch back so that commit dangles —
    # in the object store but unreachable from any branch.
    (tmp_path / "f.py").write_text("# v2\n")
    _run(
        ["git", "commit", "-am", "fix(abc123): Autonomous remediation: fix.format"],
        tmp_path,
    )
    orphan_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)
    _run(["git", "reset", "--hard", "HEAD~1"], tmp_path)
    assert not _run(["git", "branch", "--contains", orphan_sha], tmp_path).strip()

    meta = await _capture_commit_meta(str(tmp_path), orphan_sha)
    assert "fix.format" in meta["commit_subject"]
    assert meta["commit_author"] == "Test"
    assert meta["commit_date"], "ISO commit date must be captured"


@pytest.mark.asyncio
async def test_capture_meta_handles_gone_object(tmp_path: Path) -> None:
    """A sha no longer in the object store (already gc'd) yields a sentinel
    subject rather than crashing the audit run."""
    _init_repo(tmp_path)
    (tmp_path / "f.py").write_text("# v1\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)

    meta = await _capture_commit_meta(str(tmp_path), "0" * 40)
    assert "not in store" in meta["commit_subject"]
