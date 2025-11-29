# src/services/git_service.py

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

logger = getLogger(__name__)


# ID: 195434df-adc5-4e68-bb84-8962b1c5ec9c
class GitService:
    """Provides basic git operations for agents and services."""

    def __init__(self, repo_path: str | Path):
        """
        Initializes the GitService and validates the repository path.
        """
        self.repo_path = Path(repo_path).resolve()
        logger.info(f"GitService initialized for path {self.repo_path}")

    def _run_command(self, command: list[str], cwd: Path | None = None) -> str:
        """Runs a git command and returns stdout; raises RuntimeError on failure."""
        try:
            effective_cwd = cwd or self.repo_path
            logger.debug(f"Running git command: {' '.join(command)} in {effective_cwd}")
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
            logger.error(f"Git command failed: {msg}")
            raise RuntimeError(f"Git command failed: {msg}") from e

    # ID: ec16988c-6830-408c-a31c-e6799c430b08
    def init(self, path: Path):
        """Initializes a new Git repository at the specified path."""
        self._run_command(["init"], cwd=path)

    # ID: 5aeb7647-95cc-405f-b941-f52d4dd9ac81
    def get_current_commit(self) -> str:
        """Returns the hash of the current HEAD commit."""
        return self._run_command(["rev-parse", "HEAD"])

    # ID: 7caf2626-1af7-40fb-ad83-c44f4816b054
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

    # ID: e00621cc-976b-4418-857c-9c9783a09c0c
    def is_git_repo(self) -> bool:
        """Returns True if a '.git' directory exists."""
        return (self.repo_path / ".git").exists()

    # ID: 9375ce45-24db-4e25-885b-6d268a7c1324
    def status_porcelain(self) -> str:
        """Returns the porcelain status output."""
        return self._run_command(["status", "--porcelain"])

    # ID: ba274efa-20af-4e82-9886-20f132465125
    def add_all(self) -> None:
        """Stages all changes, including untracked files."""
        self._run_command(["add", "-A"])

    # --- FIX: Added missing add() method ---
    # ID: ac30b490-2ee4-41ae-93c6-a06ad5a72db0
    def add(self, path: str | Path) -> None:
        """Stages a specific file."""
        self._run_command(["add", str(path)])

    # ---------------------------------------

    # ID: f95573be-ebc4-4d48-bc3c-0187edb982ef
    def commit(self, message: str) -> None:
        """
        Commits staged changes with the provided message.
        """
        try:
            self.add_all()
            if not self.get_staged_files():
                logger.info("No changes staged to commit.")
                return
            self._run_command(["commit", "-m", message])
            logger.info(f"Committed changes with message: '{message}'")
        except RuntimeError as e:
            emsg = (str(e) or "").lower()
            if "nothing to commit" in emsg or "no changes added to commit" in emsg:
                logger.info("No changes staged. Skipping commit.")
                return
            raise
