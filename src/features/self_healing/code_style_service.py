# src/features/self_healing/code_style_service.py
"""
Provides the service logic for formatting code according to constitutional style rules.
"""

from __future__ import annotations

from shared.utils.subprocess_utils import run_poetry_command


# ID: 5c5890b0-8c2f-4d9a-a4e2-0f7b6a5c4e3b
def format_code(path: str | None = None):
    """
    Format code using Black and Ruff, optionally targeting a specific file or directory.
    If no path is provided, it defaults to formatting 'src' and 'tests'.
    """
    targets = [path] if path else ["src", "tests"]

    run_poetry_command(
        f"✨ Formatting {' '.join(targets)} with Black...", ["black", *targets]
    )
    run_poetry_command(
        f"✨ Fixing {' '.join(targets)} with Ruff...",
        ["ruff", "check", "--fix", *targets],
    )
