# src/features/self_healing/code_style_service.py
"""
Provides the service logic for formatting code according to constitutional style rules.
"""

from __future__ import annotations

from shared.utils.subprocess_utils import run_poetry_command


# ID: 5c5890b0-8c2f-4d9a-a4e2-0f7b6a5c4e3b
def format_code():
    """Format all code in the `src` and `tests` directories using Black and Ruff with automatic fixes."""
    run_poetry_command("✨ Formatting code with Black...", ["black", "src", "tests"])
    run_poetry_command(
        "✨ Fixing code with Ruff...", ["ruff", "check", "src", "tests", "--fix"]
    )
