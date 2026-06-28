# src/shared/infrastructure/git_service.py

"""
GitService: thin, testable wrapper around git commands used by CORE.

Responsibilities
- Validate repo path and .git presence on init.
- Provide small, composable operations (status, add, commit, etc.).
- Raise RuntimeError with useful stderr/stdout on git failures.

Constitutional sanctuary: this module is the sole permitted user of
subprocess for git operations. All other layers must go through this service.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from datetime import date
from pathlib import Path

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG_GIT = load_operational_config().git

# ADR-071 D2.2 Phase 1: hermetic action execution via git worktree.
# Sandbox worktrees live under SANDBOX_PARENT (repo-relative) with names
# beginning SANDBOX_PREFIX so the orphan sweep on daemon boot can identify
# and reclaim them without touching unrelated worktrees.
# /tmp is prohibited per CLAUDE.md; all temp writes use var/tmp/.
SANDBOX_PARENT = Path("var/tmp")
SANDBOX_PREFIX = "core-action-sandbox-"


# ID: 4c70a9c7-ee57-40d7-80af-470c19223c21
class GitService:
    """Provides basic git operations for agents and services."""

    def __init__(self, repo_path: str | Path):
        """
        Initializes the GitService and validates the repository path.
        """
        self.repo_path = Path(repo_path).resolve()
        logger.info("GitService initialized for path %s", self.repo_path)

    def _run_command(self, command: list[str], cwd: Path | None = None) -> str:
        """Runs a git command and returns stdout; raises RuntimeError on failure."""
        try:
            effective_cwd = cwd or self.repo_path
            logger.debug(
                "Running git command: {' '.join(command)} in %s", effective_cwd
            )
            result = subprocess.run(
                ["git", *command],
                cwd=effective_cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            msg = e.stderr or e.stdout or ""
            logger.error("Git command failed: %s", msg)
            raise RuntimeError(f"Git command failed: {msg}") from e

    # ID: 06b9d4c8-a43e-4430-9f34-08d45747674a
    def init(self, path: Path):
        """Initializes a new Git repository at the specified path."""
        self._run_command(["init"], cwd=path)

    # ID: cc819226-e33c-4559-a2d6-88d5d9e0ddaa
    def get_current_commit(self) -> str:
        """Returns the hash of the current HEAD commit."""
        return self._run_command(["rev-parse", "HEAD"])

    # ID: e7a5c19d-2f48-4b6c-9d3a-1f0b4e8c5d72
    def get_current_branch(self) -> str:
        """
        Returns the current branch name (e.g. 'main').

        Raises RuntimeError on failure — for example, when HEAD is detached
        or the repository has no commits yet. Callers that treat git
        metadata as optional should wrap this call.
        """
        return self._run_command(["rev-parse", "--abbrev-ref", "HEAD"])

    # ID: f8b6d2ae-3059-4c7d-ae4b-208c5f9d6e83
    def get_remote_url(self, remote: str = "origin") -> str:
        """
        Returns the configured URL for the given remote (default 'origin').

        Raises RuntimeError if the remote is not configured. Callers that
        treat the remote URL as optional should wrap this call.
        """
        return self._run_command(["remote", "get-url", remote])

    # ID: 62355f31-f9eb-4ac1-984e-eea556b29f31
    def get_staged_files(self) -> list[str]:
        """Returns a list of files that are currently staged for commit."""
        try:
            output = self._run_command(
                ["diff", "--cached", "--name-only", "--diff-filter=ACMR"]
            )
            if not output:
                return []
            return output.splitlines()
        except RuntimeError:
            return []

    # ID: e506910f-2fc8-41ac-8f77-4dd79da1e6c6
    def is_git_repo(self) -> bool:
        """Returns True if a '.git' directory exists."""
        return (self.repo_path / ".git").exists()

    # ID: 1fdc163e-5305-462d-8fb2-7097172a1f40
    def is_committed(self, rel_path: str | Path) -> bool:
        """Return True if rel_path exists in the HEAD commit tree.

        Uses ``git ls-tree HEAD`` rather than ``ls-files`` so that staged-but-
        not-committed files return False — matching the set of files that would
        be present in a sandbox worktree created at HEAD (ADR-071 D2.2).
        """
        try:
            output = self._run_command(
                ["ls-tree", "--name-only", "HEAD", "--", str(rel_path)]
            )
            return bool(output.strip())
        except RuntimeError:
            return False

    # ID: 715fe14e-e905-4032-9721-35bc67639ed7
    def status_porcelain(self) -> str:
        """Returns the porcelain status output."""
        return self._run_command(["status", "--porcelain"])

    # ID: db520983-cdb8-4b99-a1d9-60467128b6dc
    def add_all(self) -> None:
        """Stages all changes, including untracked files.

        Intended for manual/CLI callers (governor-driven flows) that
        legitimately want to capture every working-tree change.
        Autonomous workers must NOT use this — they must use
        ``add(path)`` or ``commit_paths(paths, message)`` so their
        commits are scoped to declared files and cannot accidentally
        sweep in unrelated working-tree changes (debug edits, partial
        WIP, other workers' artifacts).
        """
        self._run_command(["add", "-A"])

    # ID: 823668c8-17fc-4472-9d37-b22735b8d018
    def add(self, path: str | Path) -> None:
        """Stages a specific file."""
        self._run_command(["add", str(path)])

    # ID: 3acb0e63-e71b-4eba-a5ed-88e8e4eec35d
    def commit(self, message: str) -> None:
        """
        Commits all changes with the provided message.

        Stages all changes (``git add -A``) before committing. If the first
        commit attempt fails because a pre-commit hook modified files (hooks
        exit non-zero and rewrite staged content), stages again and retries
        once. This is the standard two-pass pattern required when pre-commit
        hooks auto-fix files.

        Intended for manual/CLI callers (governor-driven flows) that
        legitimately want to capture every working-tree change in a single
        commit. Autonomous workers must NOT use this — they must use
        ``commit_paths(paths, message)`` so their commits are scoped to
        declared files and cannot accidentally sweep in unrelated
        working-tree changes (debug edits, partial WIP, other workers'
        artifacts).
        """
        self._run_command(["add", "-A"])
        try:
            self._run_command(["commit", "-m", message])
        except RuntimeError as first_err:
            # Pre-commit hooks can modify files and exit non-zero on the first
            # pass. Stage their changes and retry exactly once.
            logger.info(
                "GitService: first commit attempt failed — "
                "re-staging after pre-commit hook modifications and retrying: %s",
                first_err,
            )
            self._run_command(["add", "-A"])
            self._run_command(["commit", "-m", message])

    # ID: d4e5f6a7-b8c9-0123-4567-89abcdef0123
    def restore_paths(self, paths: list[str]) -> None:
        """
        Reverts the working-tree state of the given tracked paths to HEAD.

        Used by ProposalExecutor's failure branches per ADR-021 D2/D4.
        Untracked paths in the input are silently dropped (consistent with
        `git checkout -- <pathspec>` semantics).
        """
        if not paths:
            logger.debug("GitService.restore_paths: no paths to restore")
            return

        ls_output = self._run_command(["ls-files", "--", *paths])
        tracked = [line for line in ls_output.splitlines() if line]

        if not tracked:
            logger.info(
                "GitService.restore_paths: no tracked paths in input (count_input=%d)",
                len(paths),
            )
            return

        self._run_command(["checkout", "--", *tracked])
        logger.info("GitService.restore_paths: reverted %d paths", len(tracked))

    def _get_staged_paths(self) -> set[str]:
        """Return paths currently staged in the index (git diff --cached --name-only)."""
        output = self._run_command(["diff", "--cached", "--name-only"])
        return {line for line in output.splitlines() if line}

    # ID: e5f6a7b8-c9d0-1234-5678-9abcdef01234
    def commit_paths(self, paths: list[str], message: str) -> None:
        """
        Stages and commits exactly the given paths.

        Used by ProposalExecutor's success branches per ADR-021 D3. Mirrors
        the two-pass retry pattern in `commit` for pre-commit hook
        auto-modifications.

        ADR-129 D1: two-layer protection against staging contamination.

        Layer 1 — early check: before staging anything, verifies that the
        index contains no paths outside the production set. A concurrent
        session that has staged work would otherwise be swept into the
        autonomous commit, silently violating ADR-101 D1. The check raises
        rather than clears — clearing would destroy the session's staged
        work; raising makes the violation visible so the operator can commit
        or restore their staged changes before the next daemon cycle.

        Layer 2 — structural restriction: the commit command passes the
        production paths as a pathspec (``git commit -m msg -- p1 p2 …``).
        This tells git to commit only the staged changes for those specific
        paths, regardless of what else is in the index. Belt-and-suspenders:
        even if something slips into staging in the nanosecond window between
        the check and the ``git add``, the pathspec ensures only production
        bytes enter the commit object.
        """
        if not paths:
            raise ValueError(
                "commit_paths requires at least one path; an autonomous "
                "proposal that resolved to no files is malformed"
            )

        # ADR-129 D1 Layer 1: early contamination check.
        staged = self._get_staged_paths()
        production = set(paths)
        extra = staged - production
        if extra:
            extra_sample = sorted(extra)[:3]
            raise RuntimeError(
                f"ADR-129 D1: staging area has {len(extra)} path(s) outside "
                f"the declared production set — refusing autonomous commit to "
                f"prevent authorship contamination. Commit or restore staged "
                f"work first: {extra_sample}"
                f"{'...' if len(extra) > 3 else ''}"
            )

        # ADR-129 D1 Layer 2: pathspec-restricted commit.
        self._run_command(["add", "--", *paths])
        try:
            self._run_command(["commit", "-m", message, "--", *paths])
        except RuntimeError as first_err:
            logger.info(
                "GitService.commit_paths: first commit attempt failed — "
                "re-staging after pre-commit hook modifications and retrying: %s",
                first_err,
            )
            self._run_command(["add", "--", *paths])
            self._run_command(["commit", "-m", message, "--", *paths])

    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567892
    def get_recent_commits(self, n: int = _CFG_GIT.recent_commits_n) -> list[str]:
        """
        Returns the last n commit summaries (oneline, no merges).
        Used by SystemContextGatherer for change context (Dimension 5).
        """
        try:
            output = self._run_command(["log", f"-{n}", "--oneline", "--no-merges"])
            return output.splitlines() if output else []
        except RuntimeError:
            return []

    # ID: ff02b770-4928-4a10-9358-c6df84ff091f
    def get_diff_stat(self, base: str = "HEAD~5", target: str = "HEAD") -> str:
        """
        Returns the diffstat between two refs.
        Used by SystemContextGatherer for change context (Dimension 5).
        """
        try:
            return self._run_command(["diff", "--stat", base, target])
        except RuntimeError:
            return ""

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789003
    def get_changed_files_log(self, n: int = _CFG_GIT.changed_files_log_n) -> list[str]:
        """
        Returns filenames touched in the last n commits (Python files only).
        Used by SystemContextGatherer for change context (Dimension 5).
        """
        try:
            output = self._run_command(
                ["log", "--name-only", "--pretty=format:", f"-{n}"]
            )
            return [
                line.strip()
                for line in output.splitlines()
                if line.strip() and line.strip().endswith(".py")
            ]
        except RuntimeError:
            return []

    # ID: 9f1e8c4a-5b73-4d29-a6f0-2c8e7b5d1a93
    def first_seen_date(self, rel_path: str) -> date | None:
        """Return the date the file at *rel_path* was first added to git, or None.

        Runs ``git log --diff-filter=A --format=%aI -- <rel_path>`` and parses
        the OLDEST author-date returned. git log outputs in reverse chrono
        order; the last line is the oldest matching commit, which for the
        --diff-filter=A filter is the original add (re-adds after deletion
        appear later in chrono and earlier in the output). Used by
        ROW4_NAMING coherence check (per ADR-073 D6 / topology §10.2) to
        derive the grandfather signal — artifacts whose first-seen date
        predates topology paper acceptance are permitted regardless of
        D-text naming coverage.

        Fail-soft: returns None on git error, missing file, unparseable date,
        or any other failure. The caller (ROW4_NAMING) treats "unknown
        first-seen" as ungrandfathered.
        """
        try:
            output = self._run_command(
                ["log", "--diff-filter=A", "--format=%aI", "--", rel_path]
            )
        except RuntimeError:
            return None
        lines = output.splitlines() if output else []
        if not lines:
            return None
        oldest = lines[-1]
        try:
            return date.fromisoformat(oldest[:10])
        except ValueError:
            return None

    # ID: 2204a851-0f11-495b-be3d-c0af82bb13ee
    def create_worktree(self, sha: str) -> ScopedGitService:
        """
        Create a hermetic git worktree rooted at `sha` for action execution.

        Path: SANDBOX_PARENT/SANDBOX_PREFIX<uuid4>/. Uses --detach so no
        branch is created. Returns a ScopedGitService wrapping the worktree;
        the caller MUST call cleanup() (or use as a context manager). Any
        leaked worktrees are reclaimed by sweep_orphan_worktrees() on the
        next daemon boot.

        ADR-071 D2.2 Phase 1.
        """
        sandbox_parent = (self.repo_path / SANDBOX_PARENT).resolve()
        sandbox_parent.mkdir(parents=True, exist_ok=True)
        worktree_path = sandbox_parent / f"{SANDBOX_PREFIX}{uuid.uuid4().hex}"
        self._run_command(["worktree", "add", "--detach", str(worktree_path), sha])
        logger.info(
            "GitService: created worktree %s at sha %s",
            worktree_path,
            sha[:12],
        )
        return ScopedGitService(worktree_path, parent=self)

    # ID: 7990798e-4c6b-4aff-a8ce-26f7f1f9d480
    def sweep_orphan_worktrees(self) -> int:
        """
        Remove any sandbox worktrees left behind by crashed actions.

        Lists worktrees registered against this repo, removes those whose
        path lives directly under SANDBOX_PARENT with the SANDBOX_PREFIX,
        and prunes the administrative entries. Returns the count removed.
        Safe to call on daemon boot; failures are logged and swallowed so
        ignition is never blocked.

        ADR-071 D2.2 Phase 1.
        """
        try:
            output = self._run_command(["worktree", "list", "--porcelain"])
        except RuntimeError as exc:
            logger.warning("GitService.sweep_orphan_worktrees: list failed: %s", exc)
            return 0

        sandbox_parent = (self.repo_path / SANDBOX_PARENT).resolve()
        removed = 0
        for line in output.splitlines():
            if not line.startswith("worktree "):
                continue
            path_str = line[len("worktree ") :].strip()
            path = Path(path_str)
            if path.parent != sandbox_parent or not path.name.startswith(
                SANDBOX_PREFIX
            ):
                continue
            try:
                self._run_command(["worktree", "remove", "--force", path_str])
                removed += 1
                logger.info("GitService: removed orphan worktree %s", path_str)
            except RuntimeError as exc:
                logger.warning(
                    "GitService: failed to remove orphan worktree %s: %s",
                    path_str,
                    exc,
                )

        try:
            self._run_command(["worktree", "prune"])
        except RuntimeError as exc:
            logger.debug("GitService.sweep_orphan_worktrees: prune failed: %s", exc)

        return removed


# ID: ea3110a9-3a63-402f-af22-61f1860eff2b
class ScopedGitService(GitService):
    """GitService bound to a temporary git worktree (ADR-071 D2.2 Phase 1).

    Inherits every GitService operation; because `self.repo_path` points at
    the worktree, all commands execute against the sandbox rather than the
    main tree. The caller is responsible for `cleanup()` — either directly
    or via context-manager use — once execution finishes.
    """

    def __init__(self, worktree_path: Path, parent: GitService):
        super().__init__(worktree_path)
        self._parent = parent
        self._cleaned_up = False

    # ID: 375faa32-d545-47ee-9fdb-3894b425de5a
    def cleanup(self) -> None:
        """
        Remove the worktree. Idempotent. Uses `git worktree remove --force`
        which discards any uncommitted changes in the sandbox — intentional,
        because the caller is expected to copy out wanted changes before
        cleanup.
        """
        if self._cleaned_up:
            return
        try:
            self._parent._run_command(
                ["worktree", "remove", "--force", str(self.repo_path)]
            )
        except RuntimeError as exc:
            logger.warning(
                "ScopedGitService.cleanup: git worktree remove failed (%s); "
                "falling back to rmtree on %s",
                exc,
                self.repo_path,
            )
            if self.repo_path.exists():
                shutil.rmtree(self.repo_path, ignore_errors=True)
        finally:
            self._cleaned_up = True
            logger.info("ScopedGitService: cleaned up worktree %s", self.repo_path)

    def __enter__(self) -> ScopedGitService:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.cleanup()
