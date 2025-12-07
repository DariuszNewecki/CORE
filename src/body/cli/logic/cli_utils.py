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


async def _find_test_file_for_capability_async(
    capability_name: str, search_paths: list[str] | None = None
) -> Path | None:
    """
    Asynchronously find the test file associated with a given capability name.

    Args:
        capability_name: The name of the capability to find tests for
        search_paths: Optional list of paths to search in. If None, uses default paths.

    Returns:
        Path to the test file if found, None otherwise
    """
    if search_paths is None:
        search_paths = [
            "tests",
            "test",
            "src/tests",
        ]

    # Common test file patterns
    patterns = [
        f"test_{capability_name}.py",
        f"{capability_name}_test.py",
        f"test{capability_name}.py",
    ]

    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue

        for root, dirs, files in os.walk(search_path):
            for pattern in patterns:
                if pattern in files:
                    return Path(root) / pattern

            # Also check for capability name in subdirectories
            for file in files:
                if file.endswith(".py") and capability_name.lower() in file.lower():
                    return Path(root) / file

    return None


# ID: fe11b579-66f5-4aaf-bd91-636ce01604ad
def find_source_file(
    symbol_name: str, search_paths: list[str] | None = None
) -> Path | None:
    """
    Find the source file containing a given symbol.

    Args:
        symbol_name: The name of the symbol to find
        search_paths: Optional list of paths to search in. If None, uses default paths.

    Returns:
        Path to the source file if found, None otherwise
    """
    if search_paths is None:
        search_paths = ["src", "lib", "."]

    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue

        for root, dirs, files in os.walk(search_path):
            # Skip test directories
            if "test" in root.lower():
                continue

            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            content = f.read()
                            if (
                                f"def {symbol_name}" in content
                                or f"class {symbol_name}" in content
                            ):
                                return file_path
                    except Exception as e:
                        logger.debug(f"Error reading {file_path}: {e}")
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
    logger.info(f"Rollback plan archived to {archive_path}")


# ID: 0babc74d-bd4e-4cbd-8cd6-bc955b32967e
def should_fail(report: dict, fail_on: str) -> bool:
    """
    Determines if the CLI should exit with an error code based on the drift
    report and the specified fail condition.
    """
    if fail_on == "missing":
        return bool(report.get("missing_in_code"))
    if fail_on == "undeclared":
        return bool(report.get("undeclared_in_manifest"))
    return bool(
        report.get("missing_in_code")
        or report.get("undeclared_in_manifest")
        or report.get("mismatched_mappings")
    )
