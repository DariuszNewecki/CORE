# src/body/cli/logic/knowledge_sync/verify.py
"""
Verifies the integrity of exported YAML files by checking their digests.
"""

from __future__ import annotations

import logging

from shared.config import settings

from .utils import compute_digest, read_yaml

logger = logging.getLogger(__name__)
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"


# ID: 19b318e0-903d-4f25-8948-2c2680856ba1
def run_verify() -> bool:
    """Checks digests of exported YAML files to ensure integrity.

    Returns:
        bool: True if all digests are valid, False otherwise.
    """
    if not EXPORT_DIR.exists():
        logger.error(f"Export directory not found: {EXPORT_DIR}. Cannot verify.")
        return False

    logger.info("Verifying digests of exported YAML files...")

    files_to_check = [
        "capabilities.yaml",
        "symbols.yaml",
        "links.yaml",
        "northstar.yaml",
    ]
    all_ok = True

    for filename in files_to_check:
        path = EXPORT_DIR / filename
        if not path.exists():
            logger.warning(f"SKIP: {filename} does not exist.")
            continue

        doc = read_yaml(path)
        items = doc.get("items", [])
        expected_digest = doc.get("digest")

        if not expected_digest:
            logger.error(f"FAIL: {filename} is missing a digest.")
            all_ok = False
            continue

        actual_digest = compute_digest(items)

        if expected_digest == actual_digest:
            logger.info(f"PASS: {filename} digest is valid.")
        else:
            logger.error(f"FAIL: {filename} digest mismatch!")
            all_ok = False

    if all_ok:
        logger.info("All digests are valid.")
    else:
        logger.error("One or more digests failed verification.")

    return all_ok
