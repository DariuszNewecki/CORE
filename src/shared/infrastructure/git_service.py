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

import subprocess
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


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

    # ID: 715fe14e-e905-4032-9721-35bc67639ed7
    def status_porcelain(self) -> str:
        """Returns the porcelain status output."""
        return self._run_command(["status", "--porcelain"])

    # ID: db520983-cdb8-4b99-a1d9-60467128b6dc
    def add_all(self) -> None:
        """Stages all changes, including untracked files."""
        self._run_command(["add", "-A"])

    # ID: 823668c8-17fc-4472-9d37-b22735b8d018
    def add(self, path: str | Path) -> None:
        """Stages a specific file."""
        self._run_command(["add", str(path)])

    # ID: 3acb0e63-e71b-4eba-a5ed-88e8e4eec35d
    def commit(self, message: str) -> None:
        """
        Commits all changes with the provided message.

        Stages all changes before committing. If the first commit attempt fails
        because a pre-commit hook modified files (hooks exit non-zero and rewrite
        staged content), stages again and retries once. This is the standard
        two-pass pattern required when pre-commit hooks auto-fix files.
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

    # ID: e5f6a7b8-c9d0-1234-5678-9abcdef01234
    def commit_paths(self, paths: list[str], message: str) -> None:
        """
        Stages and commits exactly the given paths.

        Used by ProposalExecutor's success branches per ADR-021 D3. Mirrors
        the two-pass retry pattern in `commit` for pre-commit hook
        auto-modifications.
        """
        if not paths:
            raise ValueError(
                "commit_paths requires at least one path; an autonomous "
                "proposal that resolved to no files is malformed"
            )

        self._run_command(["add", "--", *paths])
        try:
            self._run_command(["commit", "-m", message])
        except RuntimeError as first_err:
            logger.info(
                "GitService.commit_paths: first commit attempt failed — "
                "re-staging after pre-commit hook modifications and retrying: %s",
                first_err,
            )
            self._run_command(["add", "--", *paths])
            self._run_command(["commit", "-m", message])

    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567892
    def get_recent_commits(self, n: int = 10) -> list[str]:
        """
        Returns the last n commit summaries (oneline, no merges).
        Used by SystemContextGatherer for change context (Dimension 5).
        """
        try:
            output = self._run_command(["log", f"-{n}", "--oneline", "--no-merges"])
            return output.splitlines() if output else []
        except RuntimeError:
            return []

    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678902
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
    def get_changed_files_log(self, n: int = 20) -> list[str]:
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
