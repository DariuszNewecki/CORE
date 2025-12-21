# src/body/cli/logic/cli_utils.py
"""
Provides centralized, reusable utilities for standardizing the console output
and execution of all `core-admin` commands.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)

# Directories we should not traverse when doing broad filesystem scans.
# Keep this conservative; callers can override search_paths if needed.
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


async def _find_test_file_for_capability_async(
    capability_name: str,
    search_paths: list[str] | None = None,
) -> Path | None:
    """
    Asynchronously find a test file associated with a given capability name.

    Args:
        capability_name: The name of the capability to find tests for.
        search_paths: Optional list of paths to search in. If None, uses defaults.

    Returns:
        Path to the test file if found, None otherwise.
    """
    if search_paths is None:
        search_paths = ["tests", "test", "src/tests"]

    capability_lower = capability_name.lower()

    patterns = {
        f"test_{capability_name}.py",
        f"{capability_name}_test.py",
        f"test{capability_name}.py",
    }

    for base in search_paths:
        base_path = Path(base)
        if not base_path.exists():
            continue

        for root, _dirs, files in os.walk(base_path):
            if _is_excluded_dir(root):
                continue

            # First pass: exact common patterns
            for pattern in patterns:
                if pattern in files:
                    return Path(root) / pattern

            # Second pass: capability name appears in filename
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                if capability_lower in filename.lower():
                    return Path(root) / filename

    return None


# ID: fe11b579-66f5-4aaf-bd91-636ce01604ad
def find_source_file(
    symbol_name: str,
    search_paths: list[str] | None = None,
) -> Path | None:
    """
    Find the source file containing a given symbol.

    Args:
        symbol_name: The name of the symbol to find.
        search_paths: Optional list of paths to search in. If None, uses defaults.

    Returns:
        Path to the source file if found, None otherwise.
    """
    if search_paths is None:
        # Avoid "." by default; it can explode into .git/venv/etc.
        search_paths = ["src", "lib"]

    def_markers = (f"def {symbol_name}", f"class {symbol_name}")

    for base in search_paths:
        base_path = Path(base)
        if not base_path.exists():
            continue

        for root, _dirs, files in os.walk(base_path):
            # Skip test directories and known heavy/noisy directories
            if "test" in root.lower():
                continue
            if _is_excluded_dir(root):
                continue

            for filename in files:
                if not filename.endswith(".py"):
                    continue

                file_path = Path(root) / filename
                try:
                    # Stream line-by-line to avoid loading large files into memory.
                    with file_path.open("r", encoding="utf-8") as f:
                        for line in f:
                            if def_markers[0] in line or def_markers[1] in line:
                                return file_path
                except (OSError, UnicodeDecodeError) as e:
                    logger.debug("Error reading %s: %s", file_path, e, exc_info=True)
                    continue

    return None


# ID: a3d61adf-6e42-4854-a028-89a73d47c667
def save_yaml_file(path: Path, data: dict[str, Any]) -> None:
    """Saves data to a YAML file with consistent sorting."""
    import yaml

    path.write_text(yaml.dump(data, sort_keys=True), encoding="utf-8")


# ID: 4e814eab-bdc4-4d68-b13e-8c4c53269a68
def load_private_key() -> ed25519.Ed25519PrivateKey:
    """Loads the operator's private key."""
    key_path = settings.KEY_STORAGE_DIR / "private.key"
    if not key_path.exists():
        logger.error(
            "Private key not found. Please run 'core-admin keygen' to create one."
        )
        raise typer.Exit(code=1)
    return serialization.load_pem_private_key(key_path.read_bytes(), password=None)


# ID: f803faac-7a8d-40b1-84cb-659379a4b512
def archive_rollback_plan(proposal_name: str, proposal: dict[str, Any]) -> None:
    """Archives a proposal's rollback plan upon approval."""
    rollback_plan = proposal.get("rollback_plan")
    if not rollback_plan:
        return

    rollbacks_dir = settings.MIND / "constitution" / "rollbacks"
    rollbacks_dir.mkdir(parents=True, exist_ok=True)

    archive_path = (
        rollbacks_dir
        / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{proposal_name}.json"
    )
    archive_path.write_text(
        json.dumps(
            {
                "proposal_name": proposal_name,
                "target_path": proposal.get("target_path"),
                "justification": proposal.get("justification"),
                "rollback_plan": rollback_plan,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Rollback plan archived to %s", archive_path)


# ID: 0babc74d-bd4e-4cbd-8cd6-bc955b32967e
def should_fail(report: dict[str, Any], fail_on: str) -> bool:
    """
    Determines if the CLI should exit with an error code based on the drift
    report and the specified fail condition.
    """
    missing_in_code = bool(report.get("missing_in_code"))
    undeclared_in_manifest = bool(report.get("undeclared_in_manifest"))
    mismatched_mappings = bool(report.get("mismatched_mappings"))

    if fail_on == "missing":
        return missing_in_code
    if fail_on == "undeclared":
        return undeclared_in_manifest

    # default: fail on any drift
    return missing_in_code or undeclared_in_manifest or mismatched_mappings
