# src/features/self_healing/policy_id_service.py
# ID: c1a2b3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d

"""
Provides the service logic for the one-time constitutional migration to add
UUIDs to all policy files, bringing them into compliance with the updated policy_schema.

Refactored to use the canonical ActionExecutor Gateway for all mutations.

CONSTITUTIONAL COMPLIANCE:
- Searches .intent/ structure for policy-like documents
- Uses ActionExecutor for all mutations (IntentGuard enforced)
- Dry-run by default (safe-by-default principle)

NOTE: With new .intent/ structure, "policies" are now in:
- .intent/phases/ (workflow phases)
- .intent/workflows/ (workflow definitions)
- .intent/rules/ (atomic governance rules)
This service may need to be adapted based on which files require policy_id fields.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import yaml

from body.atomic.executor import ActionExecutor
from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: bbeb523a-9777-48ae-b26e-0b37e90b0f70
async def add_missing_policy_ids(context: CoreContext, dry_run: bool = True) -> int:
    """
    Scans all constitutional policy files and adds a `policy_id` UUID via the Action Gateway.

    FIXED: Updated to search new .intent/ structure.
    Searches phases/, workflows/, and rules/ directories for policy-like documents.

    Args:
        context: CoreContext (Required for ActionExecutor)
        dry_run: If True, only reports on the changes (write=False in Gateway).

    Returns:
        The total number of policies that were (or would be) updated.
    """
    executor = ActionExecutor(context)

    # FIXED: Search new .intent/ structure
    # Policy-like documents may be in multiple locations now
    intent_root = settings.paths.intent_root

    search_dirs = [
        intent_root / "phases",
        intent_root / "workflows",
        intent_root / "rules",
    ]

    files_to_process = []
    for search_dir in search_dirs:
        if search_dir.is_dir():
            # Search for YAML files that might need policy_id
            files_to_process.extend(search_dir.rglob("*.yaml"))
            files_to_process.extend(search_dir.rglob("*.yml"))

    if not files_to_process:
        logger.info("No policy files found in .intent/ structure")
        return 0

    policies_updated = 0

    logger.info("Scanning %d policy file(s) for missing IDs...", len(files_to_process))

    for file_path in files_to_process:
        try:
            content = file_path.read_text("utf-8")
            # Use safe_load to check for the key's existence
            data = yaml.safe_load(content) or {}

            # Skip files that already have policy_id
            if "policy_id" in data:
                continue

            # Skip files that are clearly not policy documents
            # (e.g., simple configuration without structure)
            if not isinstance(data, dict) or len(data) < 2:
                continue

            # If the key is missing, prepare the fix
            new_id = str(uuid.uuid4())
            new_content = f"policy_id: {new_id}\n{content}"

            # Convert to repo-relative path for the Action Gateway
            rel_path = str(file_path.relative_to(settings.REPO_PATH))

            # CONSTITUTIONAL GATEWAY:
            # This write is now governed by IntentGuard and logged in action_results.
            result = await executor.execute(
                action_id="file.edit",
                write=not dry_run,
                file_path=rel_path,
                code=new_content,
            )

            if result.ok:
                policies_updated += 1
                status = "Added" if not dry_run else "Proposed (Dry Run)"
                logger.info(
                    "  -> [%s] policy_id=%s to %s", status, new_id, file_path.name
                )
            else:
                logger.error(
                    "  -> [BLOCKED] %s: %s", file_path.name, result.data.get("error")
                )

        except Exception as e:
            logger.error("Error processing %s: %s", file_path.name, e)

    logger.info(
        "Policy ID migration complete: %d files updated (dry_run=%s)",
        policies_updated,
        dry_run,
    )

    return policies_updated
