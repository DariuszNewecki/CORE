# src/body/cli/commands/fix_governed.py

"""
Fix Commands with Constitutional Governance Integration.

Extends existing fix commands with governance checks before execution.
All file modifications validated against constitutional rules.
"""

from __future__ import annotations

from typing import Any

import typer

from mind.governance.validator_service import can_execute_autonomously
from shared.logger import getLogger


logger = getLogger(__name__)
app = typer.Typer(
    name="fix-governed", help="Fix code issues with governance validation"
)


@app.command()
# ID: e8309edb-d090-4e12-a953-50b7c0755b51
def docstrings(
    paths: list[str] = typer.Argument(..., help="Paths to fix"),
    dry_run: bool = typer.Option(False, help="Show what would be fixed"),
):
    """
    Fix missing or malformed docstrings with governance checks.

    Args:
        paths: List of file paths to process
        dry_run: If True, show changes without applying them
    """
    logger.info("🔍 Checking governance approval...")
    blocked_files = _check_governance_for_paths(paths, "fix_docstring", dry_run)
    if blocked_files:
        _report_blocked_files(blocked_files)
        if len(blocked_files) == len(paths):
            logger.info("\n🚫 All files blocked. No actions taken.")
            raise typer.Exit(1)
        allowed_count = len(paths) - len(blocked_files)
        logger.info("\n✅ Proceeding with %s allowed files...", allowed_count)
    allowed_paths = [p for p in paths if not any(p == bf[0] for bf in blocked_files)]
    _execute_fix_docstrings(allowed_paths, dry_run)


def _check_governance_for_paths(
    paths: list[str], action: str, dry_run: bool
) -> list[tuple[str, Any]]:
    """
    Check governance for each file path.

    Args:
        paths: List of file paths to check
        action: Action to perform
        dry_run: Whether this is a dry run

    Returns:
        List of (filepath, decision) tuples for blocked files
    """
    blocked_files = []
    for path_str in paths:
        decision = can_execute_autonomously(
            filepath=path_str, action=action, context={"dry_run": dry_run}
        )
        if not decision.allowed:
            blocked_files.append((path_str, decision))
            logger.warning("🚫 Governance blocked: %s - {decision.rationale}", path_str)
    return blocked_files


def _report_blocked_files(blocked_files: list[tuple[str, Any]]):
    """
    Report files blocked by governance.

    Args:
        blocked_files: List of (filepath, decision) tuples
    """
    logger.info("\n⚠️  Some files blocked by governance:\n")
    for filepath, decision in blocked_files:
        logger.info("   %s: {decision.rationale}", filepath)


def _execute_fix_docstrings(paths: list[str], dry_run: bool):
    """
    Execute docstring fixes on allowed paths.

    Args:
        paths: List of allowed file paths
        dry_run: Whether to actually apply changes
    """
    logger.info("Would fix docstrings in %s files", len(paths))
    if dry_run:
        logger.info("(Dry run - no changes made)")


if __name__ == "__main__":
    app()
