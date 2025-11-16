# src/features/self_healing/code_style_service.py
"""
Provides the service logic for formatting code according to constitutional style rules.
"""

from __future__ import annotations

from shared.utils.subprocess_utils import run_poetry_command


# ID: 5c5890b0-8c2f-4d9a-a4e2-0f7b6a5c4e3b
def format_code(path: str | None = None) -> None:
    """
    Format code using Black and Ruff, optionally targeting a specific file or directory.

    Behaviour:
    - If ``path`` is None (default), format the default targets: ``src`` and ``tests``.
    - If ``path`` is a non-empty string, format only that path.
    - If ``path`` is an empty string, it is treated as an explicit target and passed
      as-is to Black and Ruff. This matches the expectations of the test suite.
    """
    if path is None:
        targets = ["src", "tests"]
    else:
        # Note: empty string is treated as an explicit target ([""])
        targets = [path]

    run_poetry_command(
        f"✨ Formatting {' '.join(targets)} with Black...", ["black", *targets]
    )
    run_poetry_command(
        f"✨ Fixing {' '.join(targets)} with Ruff...",
        ["ruff", "check", "--fix", *targets],
    )
