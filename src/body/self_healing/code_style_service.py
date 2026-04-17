# src/body/self_healing/code_style_service.py

"""
Provides the service logic for formatting code according to constitutional style rules.

CONSTITUTIONAL FIX: Added 'write' parameter support to respect Dry Run intent.
Ensures that external tools (ruff format/ruff check) do not mutate the disk unless authorized.
"""

from __future__ import annotations

from shared.utils.subprocess_utils import run_poetry_command


# ID: 1655ba02-a26e-4f8b-847a-8e4d16acfea0
def format_code(path: str | None = None, write: bool = True) -> None:
    """
    Format code using ruff format and ruff check.

    Args:
        path: Optional specific target. Defaults to src and tests.
        write: If False, runs in check-only mode (Dry Run).
    """
    if path is None:
        targets = ["src", "tests"]
    else:
        targets = [path]

    # --- Ruff Format Configuration ---
    ruff_format_cmd = ["ruff", "format"]
    if not write:
        ruff_format_cmd.append("--check")
    ruff_format_cmd.extend(targets)

    # --- Ruff Check (Linter) Configuration ---
    ruff_cmd = ["ruff", "check"]
    if write:
        ruff_cmd.extend(["--fix", "--unsafe-fixes"])
    else:
        # In dry-run, we just want to see what would happen
        pass
    ruff_cmd.extend(targets)

    # Execute
    run_poetry_command(
        f"✨ Ruff Format ({'Write' if write else 'Check'}): {' '.join(targets)}",
        ruff_format_cmd,
    )
    run_poetry_command(
        f"✨ Ruff Check ({'Fix' if write else 'Check'}): {' '.join(targets)}", ruff_cmd
    )
