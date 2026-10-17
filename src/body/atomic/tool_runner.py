# src/body/atomic/tool_runner.py

"""Designated subprocess sanctuary for validated-diff tooling (ADR-109, ADR-141).

Provides structural backing for the ``governance.dangerous_execution_primitives``
rule: ``git apply`` and ``ruff check`` are concentrated here as the single
authorised Body sanctuary. Nothing here imports or runs candidate code: pytest
and the stateless audit (which imports the candidate's own engine) run only in
the sandbox (``body.sandbox.repo_tests``, ``body.sandbox.repo_audit``;
external review F1).

All methods operate against a hermetic worktree path supplied by the caller —
never the main working tree.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from shared.infrastructure.git_service import SAFE_GIT_OPTIONS


# ID: f8d1f6c2-4218-45eb-aa05-be4869d59da1
class ToolRunner:
    """Subprocess sanctuary for git and ruff invocations."""

    @staticmethod
    # ID: c0aba4ec-ad56-4b7f-b2f1-9235ecfce9a0
    def run_git(
        worktree: Path, *args: str, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command scoped to *worktree*.

        Git may not look above *worktree* for a repository
        (``GIT_CEILING_DIRECTORIES``): if the worktree has vanished, the
        command fails instead of acting on an enclosing repository — where
        ``git apply`` silently ignores every path outside the current
        directory and reports success.
        """
        env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(worktree).parent)}
        return subprocess.run(
            ["git", *SAFE_GIT_OPTIONS, "-C", str(worktree), *args],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    @staticmethod
    # ID: 87732bbe-11c4-42e7-959a-9a786d4ff9c8
    def run_ruff(worktree: Path, files: list[str]) -> bool:
        """Run ``ruff check`` on *files* within *worktree*. Returns True on clean."""
        proc = subprocess.run(
            ["ruff", "check", *files],
            cwd=str(worktree),
            text=True,
            capture_output=True,
            check=False,
        )
        return proc.returncode == 0

    @staticmethod
    # ID: 2da620be-9bda-496a-904b-34463fbaf6ac
    def run_ruff_paths(worktree: Path, files: list[str]) -> bool:
        """``run_ruff`` limited to *files* that exist in *worktree*.

        A patch's deleted files are in its touched set but no longer on disk;
        ruff would report them as unreadable (E902) and fail the check.
        """
        present = [f for f in files if (worktree / f).is_file()]
        return ToolRunner.run_ruff(worktree, present) if present else True
