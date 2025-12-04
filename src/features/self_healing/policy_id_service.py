# src/features/self_healing/policy_id_service.py
"""
Provides the service logic for the one-time constitutional migration to add
UUIDs to all policy files, bringing them into compliance with the updated policy_schema.
"""

from __future__ import annotations

import uuid

import yaml
from rich.console import Console
from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)
console = Console()


# ID: c1a2b3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
def add_missing_policy_ids(dry_run: bool = True) -> int:
    """
    Scans all constitutional policy files and adds a `policy_id` UUID if it's missing.

    Args:
        dry_run: If True, only reports on the changes that would be made.

    Returns:
        The total number of policies that were (or would be) updated.
    """
    policies_dir = settings.REPO_PATH / ".intent" / "charter" / "policies"
    if not policies_dir.is_dir():
        logger.info(
            f"[bold red]Policies directory not found at: {policies_dir}[/bold red]"
        )
        return 0

    files_to_process = list(policies_dir.rglob("*_policy.yaml"))
    policies_updated = 0

    logger.info(f"🔍 Scanning {len(files_to_process)} policy files for missing IDs...")

    for file_path in files_to_process:
        try:
            content = file_path.read_text("utf-8")
            # Use safe_load to check for the key's existence
            data = yaml.safe_load(content) or {}

            if "policy_id" in data:
                continue

            # If the key is missing, add it
            policies_updated += 1
            new_id = str(uuid.uuid4())

            # Prepend the new ID to the raw file content to preserve comments and structure
            new_content = f"policy_id: {new_id}\n" + content

            if dry_run:
                logger.info(
                    f"  -> [DRY RUN] Would add `policy_id: {new_id}` to [cyan]{file_path.name}[/cyan]"
                )
            else:
                file_path.write_text(new_content, "utf-8")
                logger.info(
                    f"  -> ✅ Added `policy_id` to [green]{file_path.name}[/green]"
                )

        except Exception as e:
            logger.info(
                f"  -> [bold red]❌ Error processing {file_path.name}: {e}[/bold red]"
            )

    return policies_updated
