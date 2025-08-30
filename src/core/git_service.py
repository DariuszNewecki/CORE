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


# CAPABILITY: change_safety_enforcement
class GitService:
    """Provides basic git operations for agents and services."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = str(Path(repo_path).resolve())
        git_dir = Path(self.repo_path) / ".git"
        if not git_dir.exists():
            # tests expect a ValueError when .git is missing
            raise ValueError(f"Not a git repository ('.git' missing): {self.repo_path}")
        log.info(f"GitService initialized for repo at {self.repo_path}")

    def _run_command(self, command: list[str]) -> str:
        """Runs a git command and returns stdout; raises RuntimeError on failure."""
        try:
            log.debug(f"Running git command: {' '.join(command)}")
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            # Include stderr or stdout so errors like "nothing added to commit" are visible
            msg = e.stderr or e.stdout or ""
            log.error(f"Git command failed: {msg}")
            raise RuntimeError(f"Git command failed: {msg}") from e

    # --- Basic ops ------------------------------------------------------------

    def is_git_repo(self) -> bool:
        """Returns True if a '.git' directory exists (lightweight check for tests)."""
        return (Path(self.repo_path) / ".git").exists()

    def status_porcelain(self) -> str:
        """Returns the porcelain status output."""
        return self._run_command(["git", "status", "--porcelain"])

    def add(self, file_path: str = ".") -> None:
        """Stages a file (or path)."""
        self._run_command(["git", "add", file_path])

    def add_all(self) -> None:
        """Stages all changes, including untracked files."""
        self._run_command(["git", "add", "-A"])

    def commit(self, message: str) -> None:
        """
        Commits staged changes with the provided message.
        Robust behavior:
        - If there are changes but some are untracked, auto-stage everything.
        - If there are no changes, exit gracefully.
        """
        try:
            status_output = self.status_porcelain()
            if not status_output.strip():
                log.info("No changes to commit.")
                return

            # Ensure untracked changes are staged as well (prevents common failure).
            self.add_all()
            self._run_command(["git", "commit", "-m", message])
            log.info(f"Committed changes with message: '{message}'")
        except RuntimeError as e:
            emsg = (str(e) or "").lower()
            # Tolerate benign cases (nothing staged, etc.)
            if (
                "nothing to commit" in emsg
                or "no changes added to commit" in emsg
                or "untracked files present" in emsg
            ):
                log.info("No changes staged. Skipping commit.")
                return
            raise
