# src/cli/commands/check/utils.py
"""
Utility functions for check commands.

File operations, path resolution, and other helpers.
"""

from __future__ import annotations

from pathlib import Path


# ID: daf2036c-fd67-400a-8e41-f5361944c73c
def iter_target_files(target: Path) -> list[Path]:
    """
    Resolve target into a list of files to audit.

    - If target is a file: audit that file
    - If target is a directory: audit all *.py files under it

    Returns:
        Sorted list of Python files to audit
    """
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(p for p in target.rglob("*.py") if p.is_file())
    return []
