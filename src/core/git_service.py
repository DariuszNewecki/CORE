# src/core/git_service.py
"""
GitService — CORE's Git Integration Layer

Provides safe, auditable Git operations:
- add, commit, rollback
- status checks
- branch management

Ensures all changes are tracked and reversible.
Used by main.py and self-correction engine.
"""

import subprocess
from pathlib import Path
from typing import Optional

from shared.logger import getLogger

log = getLogger(__name__)

class GitService:
    """
    Encapsulates Git operations for the CORE system.
    Ensures all file changes are committed with traceable messages.
    """

    def __init__(self, repo_path: str):
        """
        Initialize GitService with repository root.

        Args:
            repo_path (str): Path to the Git repository.
        """
        self.repo_path = Path(repo_path).resolve()
        if not self.is_git_repo():
            raise ValueError(f"Invalid Git repository: {repo_path}")
        log.info(f"GitService initialized for repo at {self.repo_path}")

    # CAPABILITY: change_safety_enforcement
    def _run_command(self, command: list) -> str:
        """
        Run a Git command and return stdout.

        Args:
            command (list): Git command as a list (e.g., ['git', 'status']).

        Returns:
            str: Command output, or raises RuntimeError on failure.
        """
        try:
            log.debug(f"Running git command: {' '.join(command)}")
            result = subprocess.run(
                command, cwd=self.repo_path, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            log.error(f"Git command failed: {e.stderr}")
            raise RuntimeError(f"Git command failed: {e.stderr}") from e

    def add(self, file_path: str = "."):
        """
        Stage a file or directory for commit.

        Args:
            file_path (str): Path to stage. Defaults to '.' (all changes).
        """
        abs_path = (self.repo_path / file_path).resolve()
        if self.repo_path not in abs_path.parents and abs_path != self.repo_path:
            raise ValueError(f"Cannot stage file outside repo: {file_path}")
        self._run_command(["git", "add", file_path])

    # --- THIS IS THE FIX ---
    # The commit method now gracefully handles the "no changes to commit" case.
    def commit(self, message: str):
        """
        Commit staged changes with a message.
        If there are no changes to commit, this operation is a no-op and will not raise an error.

        Args:
            message (str): Commit message explaining the change.
        """
        try:
            # First, check if there are any staged changes.
            status_output = self._run_command(["git", "status", "--porcelain"])
            if not status_output:
                log.info("No changes to commit.")
                return

            self._run_command(["git", "commit", "-m", message])
            log.info(f"Committed changes with message: {message}")
        except RuntimeError as e:
            # It's possible for a race condition, or for the status check to be insufficient.
            # We specifically check for the "nothing to commit" message from Git.
            if "nothing to commit" in str(e).lower():
                log.info("No changes to commit.")
            else:
                # Re-raise any other unexpected error.
                raise e

    def is_git_repo(self) -> bool:
        """
        Check if the configured path is a valid Git repository.

        Returns:
            bool: True if it's a Git repo, False otherwise.
        """
        git_dir = self.repo_path / ".git"
        return git_dir.is_dir()

    def get_current_commit(self) -> str:
        """
        Gets the full SHA hash of the current commit (HEAD).
        """
        return self._run_command(["git", "rev-parse", "HEAD"])

    def reset_to_commit(self, commit_hash: str):
        """
        Performs a hard reset to a specific commit hash.
        This will discard all current changes.
        """
        log.warning(f"Performing hard reset to commit {commit_hash}...")
        self._run_command(["git", "reset", "--hard", commit_hash])
        log.info(f"Repository reset to {commit_hash}.")