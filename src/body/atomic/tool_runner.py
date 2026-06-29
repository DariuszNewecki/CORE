# src/body/atomic/tool_runner.py

"""Designated subprocess sanctuary for validated-diff tooling (ADR-109).

Provides structural backing for the ``governance.dangerous_execution_primitives``
rule: ``git apply`` and ``ruff check`` subprocess calls are concentrated here as
the single authorised Body sanctuary, mirroring the pytest subprocess in
``shared.infrastructure.validation.test_runner``.

All methods operate against a hermetic worktree path supplied by the caller —
never the main working tree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


# ID: f8d1f6c2-4218-45eb-aa05-be4869d59da1
class ToolRunner:
    """Subprocess sanctuary for git and ruff invocations in validation worktrees."""

    @staticmethod
    # ID: c0aba4ec-ad56-4b7f-b2f1-9235ecfce9a0
    def run_git(
        worktree: Path, *args: str, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command scoped to *worktree*."""
        return subprocess.run(
            ["git", "-C", str(worktree), *args],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
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
