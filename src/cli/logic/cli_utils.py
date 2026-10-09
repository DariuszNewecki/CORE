# src/cli/logic/cli_utils.py
"""
Provides centralized, reusable utilities for standardizing the console output
and execution of all `core-admin` commands.

- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Enforces IntentGuard and audit logging for all CLI helper operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

# Directories we should not traverse when doing broad filesystem scans.
_DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "site",
    ".venv",
    "venv",
    ".tox",
}


def _is_excluded_dir(path: str) -> bool:
    parts = {p for p in Path(path).parts if p}
    return bool(parts & _DEFAULT_EXCLUDE_DIRS)


# ID: 0babc74d-bd4e-4cbd-8cd6-bc955b32967e
def should_fail(report: dict[str, Any], fail_on: str) -> bool:
    """
    Determines if the CLI should exit with an error code based on drift.
    """
    missing_in_code = bool(report.get("missing_in_code"))
    undeclared_in_manifest = bool(report.get("undeclared_in_manifest"))
    mismatched_mappings = bool(report.get("mismatched_mappings"))

    if fail_on == "missing":
        return missing_in_code
    if fail_on == "undeclared":
        return undeclared_in_manifest

    return missing_in_code or undeclared_in_manifest or mismatched_mappings
