# src/core/git_service.py
"""
GitService: thin, testable wrapper around git commands used by CORE.

Responsibilities
- Validate repo path and .git presence on init.
- Provide small, composable operations (status, add, commit, etc.).
- Raise RuntimeError with useful stderr/stdout on git failures.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.logger import getLogger

log = getLogger(__name__)


# ID: c1c9c30d-f864-4d43-8e12-d5263e52c15c
class GitService:
    """Provides basic git operations for agents and services."""

    def __init__(self, repo_path: str | Path):
        """
        Initializes the GitService and validates the repository path.
        """
        self.repo_path = Path(repo_path).resolve()

        # Allow initialization on a path that doesn't yet have .git
        # The is_git_repo() check can be used by callers.
        log.info(f"GitService initialized for path {self.repo_path}")

    def _run_command(self, command: list[str], cwd: Path | None = None) -> str:
        """Runs a git command and returns stdout; raises RuntimeError on failure."""
        try:
            effective_cwd = cwd or self.repo_path
            log.debug(f"Running git command: {' '.join(command)} in {effective_cwd}")
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
            log.error(f"Git command failed: {msg}")
            raise RuntimeError(f"Git command failed: {msg}") from e

    # ID: e8ab2870-d868-4c23-9f18-240110560b6d
    def init(self, path: Path):
        """Initializes a new Git repository at the specified path."""
        self._run_command(["init"], cwd=path)

    # ID: 41b4a07f-880b-4180-8e2e-ab7109b07ffc
    def get_current_commit(self) -> str:
        """Returns the hash of the current HEAD commit."""
        return self._run_command(["rev-parse", "HEAD"])

    # ID: eed906a4-ba54-4af9-94fe-9865d6906c96
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

    # ID: 8d60714d-0214-48a9-be5b-9011e53ad93e
    def is_git_repo(self) -> bool:
        """Returns True if a '.git' directory exists."""
        return (self.repo_path / ".git").exists()

    # ID: b5420530-081f-4fa8-9754-5a00bedd5924
    def status_porcelain(self) -> str:
        """Returns the porcelain status output."""
        return self._run_command(["status", "--porcelain"])

    # ID: 2874a643-2e40-44f0-917f-a928484b2c67
    def add_all(self) -> None:
        """Stages all changes, including untracked files."""
        self._run_command(["add", "-A"])

    # ID: 55ed0386-16c1-458a-9b8f-f3ca0dc73696
    def commit(self, message: str) -> None:
        """
        Commits staged changes with the provided message.
        """
        try:
            # Stage everything one last time to be sure
            self.add_all()
            # Check if there is anything to commit after staging
            if not self.get_staged_files():
                log.info("No changes staged to commit.")
                return

            self._run_command(["commit", "-m", message])
            log.info(f"Committed changes with message: '{message}'")
        except RuntimeError as e:
            emsg = (str(e) or "").lower()
            if "nothing to commit" in emsg or "no changes added to commit" in emsg:
                log.info("No changes staged. Skipping commit.")
                return
            raise
