"""Tests for CommitAuthorshipAuditWorker helpers (ADR-129 D4).

The diff helper previously lived as a module-level private function in
commit_authorship_audit_worker.py. It is now centralised in
GitService.diff_file_names (shared sanctuary for async git operations).
Tests moved here accordingly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.infrastructure.git_service import GitService


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> None:
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@adr129.local"], tmp_path)
    _run(["git", "config", "user.name", "ADR129 Worker Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    _run(["git", "add", "seed.txt"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)


async def test_diff_file_names_returns_changed_paths(tmp_path: Path) -> None:
    """Files changed between two SHAs are returned correctly."""
    _init_repo(tmp_path)
    pre_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    (tmp_path / "produced.py").write_text("x = 1\n")
    _run(["git", "add", "produced.py"], tmp_path)
    _run(["git", "commit", "-m", "produced"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    result = await GitService(tmp_path).diff_file_names(pre_sha, post_sha)
    assert result is not None
    assert "produced.py" in result


async def test_diff_file_names_detects_extra_files(tmp_path: Path) -> None:
    """When the commit contains files beyond the declared set, they appear."""
    _init_repo(tmp_path)
    pre_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    (tmp_path / "declared.py").write_text("a\n")
    (tmp_path / "contamination.py").write_text("b\n")
    _run(["git", "add", "declared.py", "contamination.py"], tmp_path)
    _run(["git", "commit", "-m", "two files"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    result = await GitService(tmp_path).diff_file_names(pre_sha, post_sha)
    assert result is not None
    extra = set(result) - {"declared.py"}
    assert "contamination.py" in extra


async def test_diff_file_names_returns_none_on_bad_sha(tmp_path: Path) -> None:
    """Invalid SHAs cause diff_file_names to return None rather than raising."""
    _init_repo(tmp_path)
    result = await GitService(tmp_path).diff_file_names("0" * 40, "1" * 40)
    assert result is None


async def test_diff_file_names_empty_for_no_changes(tmp_path: Path) -> None:
    """Identical SHAs yield an empty list (no diff)."""
    _init_repo(tmp_path)
    sha = _run(["git", "rev-parse", "HEAD"], tmp_path)
    result = await GitService(tmp_path).diff_file_names(sha, sha)
    assert result == []


# ---------------------------------------------------------------------------
# diff_file_names_for_commit (#811) — the proposal's own commit in isolation,
# not the pre_sha..post_sha range. Reproduces the exact false-positive shape
# reported in #811: an independently-authored commit lands between capture
# of pre_sha and the proposal's own commit.
# ---------------------------------------------------------------------------


async def test_diff_file_names_for_commit_normal_case_matches_declared(
    tmp_path: Path,
) -> None:
    """A proposal's own commit touching only its declared file(s) is clean."""
    _init_repo(tmp_path)
    (tmp_path / "declared.py").write_text("a\n")
    _run(["git", "add", "declared.py"], tmp_path)
    _run(["git", "commit", "-m", "fix(proposal): declared change"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    result = await GitService(tmp_path).diff_file_names_for_commit(post_sha)
    assert result == ["declared.py"]
    extra = set(result) - {"declared.py"}
    assert extra == set()


async def test_diff_file_names_for_commit_detects_undeclared_files_in_same_commit(
    tmp_path: Path,
) -> None:
    """Real contamination -- extra files inside the proposal's own commit --
    must still be detected; the fix narrows the diff range, not the
    comparison logic."""
    _init_repo(tmp_path)
    (tmp_path / "declared.py").write_text("a\n")
    (tmp_path / "contamination.py").write_text("b\n")
    _run(["git", "add", "declared.py", "contamination.py"], tmp_path)
    _run(["git", "commit", "-m", "fix(proposal): declared change"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    result = await GitService(tmp_path).diff_file_names_for_commit(post_sha)
    assert result is not None
    extra = set(result) - {"declared.py"}
    assert extra == {"contamination.py"}


async def test_diff_file_names_for_commit_excludes_intervening_independently_authored_commit(
    tmp_path: Path,
) -> None:
    """#811 regression: an unrelated commit landing between pre_sha capture
    and the proposal's own commit must not appear as "extra" -- it was
    never part of the proposal's diff at all.

    Reproduces the exact shape from #811: pre_sha captured, then a human/
    governor commit lands on an unrelated file, then the proposal's own
    commit lands touching only its declared file. The old
    pre_sha..post_sha range diff would have included the intervening
    commit's file as a false "extra path."
    """
    _init_repo(tmp_path)
    pre_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    # Independently authored commit, unrelated to the proposal, landing
    # between pre_sha and the proposal's own commit.
    (tmp_path / "governor_change.py").write_text("g = 1\n")
    _run(["git", "add", "governor_change.py"], tmp_path)
    _run(["git", "commit", "-m", "fix(quarantine): unrelated governor fix"], tmp_path)

    # The proposal's own commit, touching only its declared file.
    (tmp_path / "declared.py").write_text("a\n")
    _run(["git", "add", "declared.py"], tmp_path)
    _run(["git", "commit", "-m", "fix(proposal): declared change"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    # Sanity check: the old range-diff DOES span the intervening commit --
    # confirming this fixture reproduces the reported false-positive shape.
    range_diff = await GitService(tmp_path).diff_file_names(pre_sha, post_sha)
    assert range_diff is not None
    assert "governor_change.py" in range_diff

    # The fix: the proposal's own commit diff excludes it entirely.
    result = await GitService(tmp_path).diff_file_names_for_commit(post_sha)
    assert result == ["declared.py"]
    extra = set(result) - {"declared.py"}
    assert extra == set()
    assert "governor_change.py" not in result


async def test_diff_file_names_for_commit_returns_none_on_bad_sha(
    tmp_path: Path,
) -> None:
    """An invalid SHA causes diff_file_names_for_commit to return None
    rather than raising."""
    _init_repo(tmp_path)
    result = await GitService(tmp_path).diff_file_names_for_commit("1" * 40)
    assert result is None
