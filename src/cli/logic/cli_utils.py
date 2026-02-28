# src/body/cli/logic/cli_utils.py
"""
Provides centralized, reusable utilities for standardizing the console output
and execution of all `core-admin` commands.

- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Enforces IntentGuard and audit logging for all CLI helper operations.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.storage.file_handler import FileHandler

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


async def _find_test_file_for_capability_async(
    capability_name: str,
    search_paths: list[str] | None = None,
) -> Path | None:
    """
    Asynchronously find a test file associated with a given capability name.
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

            for pattern in patterns:
                if pattern in files:
                    return Path(root) / pattern

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
    """
    if search_paths is None:
        search_paths = ["src", "lib"]

    def_markers = (f"def {symbol_name}", f"class {symbol_name}")

    for base in search_paths:
        base_path = Path(base)
        if not base_path.exists():
            continue

        for root, _dirs, files in os.walk(base_path):
            if "test" in root.lower():
                continue
            if _is_excluded_dir(root):
                continue

            for filename in files:
                if not filename.endswith(".py"):
                    continue

                file_path = Path(root) / filename
                try:
                    with file_path.open("r", encoding="utf-8") as f:
                        for line in f:
                            if def_markers[0] in line or def_markers[1] in line:
                                return file_path
                except (OSError, UnicodeDecodeError) as e:
                    logger.debug("Error reading %s: %s", file_path, e, exc_info=True)
                    continue

    return None


# ID: a3d61adf-6e42-4854-a028-89a73d47c667
def save_yaml_file(path: Path, data: dict[str, Any], file_handler: FileHandler) -> None:
    """Saves data to a YAML file via the governed FileHandler."""
    import yaml

    try:
        rel_path = str(path.resolve().relative_to(file_handler.repo_path.resolve()))
        content = yaml.dump(data, sort_keys=True)
        file_handler.write_runtime_text(rel_path, content)
    except ValueError:
        logger.error(
            "Attempted to save YAML file outside repository boundary: %s", path
        )
        raise


# ID: 4e814eab-bdc4-4d68-b13e-8c4c53269a68
def load_private_key(repo_root: Path) -> ed25519.Ed25519PrivateKey:
    """
    Loads the operator's private key.
    Requires repo_root to locate .intent/keys/private.key without global settings.
    """
    key_path = repo_root / ".intent" / "keys" / "private.key"
    if not key_path.exists():
        logger.error(
            "Private key not found at %s. Please run 'core-admin manage keys generate' to create one.",
            key_path,
        )
        raise typer.Exit(code=1)
    return serialization.load_pem_private_key(key_path.read_bytes(), password=None)


# ID: f803faac-7a8d-40b1-84cb-659379a4b512
def archive_rollback_plan(
    proposal_name: str,
    proposal: dict[str, Any],
    file_handler: FileHandler,
) -> None:
    """Archives a proposal's rollback plan via the governed FileHandler."""
    rollback_plan = proposal.get("rollback_plan")
    if not rollback_plan:
        return

    rel_rollbacks_dir = "var/mind/rollbacks"
    file_handler.ensure_dir(rel_rollbacks_dir)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    archive_filename = f"{timestamp}-{proposal_name}.json"
    rel_archive_path = f"{rel_rollbacks_dir}/{archive_filename}"

    payload = {
        "proposal_name": proposal_name,
        "target_path": proposal.get("target_path"),
        "justification": proposal.get("justification"),
        "rollback_plan": rollback_plan,
    }

    file_handler.write_runtime_json(rel_archive_path, payload)
    logger.info("Rollback plan archived to %s", rel_archive_path)


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
