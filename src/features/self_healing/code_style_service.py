# src/features/self_healing/code_style_service.py
# ID: 5c5890b0-8c2f-4d9a-a4e2-0f7b6a5c4e3b

"""
Provides the service logic for formatting code according to constitutional style rules.

CONSTITUTIONAL FIX: Added 'write' parameter support to respect Dry Run intent.
Ensures that external tools (Black/Ruff) do not mutate the disk unless authorized.
"""

from __future__ import annotations

from shared.utils.subprocess_utils import run_poetry_command


# ID: 1655ba02-a26e-4f8b-847a-8e4d16acfea0
def format_code(path: str | None = None, write: bool = True) -> None:
    """
    Format code using Black and Ruff.

    Args:
        path: Optional specific target. Defaults to src and tests.
        write: If False, runs in check-only mode (Dry Run).
    """
    if path is None:
        targets = ["src", "tests"]
    else:
        targets = [path]

    # --- Black Configuration ---
    black_cmd = ["black"]
    if not write:
        black_cmd.append("--check")
    black_cmd.extend(targets)

    # --- Ruff Configuration ---
    ruff_cmd = ["ruff", "check"]
    if write:
        ruff_cmd.extend(["--fix", "--unsafe-fixes"])
    else:
        # In dry-run, we just want to see what would happen
        pass
    ruff_cmd.extend(targets)

    # Execute
    run_poetry_command(
        f"✨ Black ({'Write' if write else 'Check'}): {' '.join(targets)}", black_cmd
    )
    run_poetry_command(
        f"✨ Ruff ({'Fix' if write else 'Check'}): {' '.join(targets)}", ruff_cmd
    )
