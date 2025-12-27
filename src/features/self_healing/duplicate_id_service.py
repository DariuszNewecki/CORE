# src/features/self_healing/duplicate_id_service.py
"""
Provides a service to intelligently find and resolve duplicate UUIDs in the codebase.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mind.governance.checks.id_uniqueness_check import IdUniquenessCheck
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


async def _get_symbol_creation_dates(session: AsyncSession) -> dict[str, str]:
    """
    Queries the database to get the creation timestamp for each symbol UUID.

    Args:
        session: Database session (injected dependency)
    """
    try:
        result = await session.execute(text("SELECT id, created_at FROM core.symbols"))
        return {str(row.id): row.created_at.isoformat() for row in result}
    except Exception as e:
        logger.warning(
            "Could not fetch symbol creation dates from DB (%s). Assuming first found is original.",
            e,
        )
        return {}


# ID: 5891cbbe-ae62-4743-92fa-2e204ca5fa13
async def resolve_duplicate_ids(session: AsyncSession, dry_run: bool = True) -> int:
    """
    Finds all duplicate IDs and fixes them by assigning new UUIDs to all but the oldest symbol.

    Args:
        session: Database session (injected dependency)
        dry_run: If True, only report what would be done without making changes

    Returns:
        The number of files that were (or would be) modified.
    """
    logger.info("Scanning for duplicate UUIDs...")

    # 1. Discover duplicates using the existing auditor check
    from mind.governance.audit_context import AuditorContext

    context = AuditorContext(settings.REPO_PATH)
    uniqueness_check = IdUniquenessCheck(context)

    findings = uniqueness_check.execute()

    duplicates = [f for f in findings if f.check_id == "linkage.duplicate_ids"]

    if not duplicates:
        logger.info("No duplicate UUIDs found.")
        return 0

    logger.warning("Found %d duplicate UUID(s). Resolving...", len(duplicates))

    # 2. Get creation dates from the database to find the "original"
    symbol_creation_dates = await _get_symbol_creation_dates(session)

    files_to_modify: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for finding in duplicates:
        locations_str = finding.context.get("locations")

        # Robustly handle missing locations
        if not locations_str:
            logger.warning(
                "Finding '%s' has no location data. Skipping.", finding.message
            )
            continue

        # FIX: Prefer extracting UUID from context (structured) over message (fragile)
        duplicate_uuid = finding.context.get("uuid")

        # Fallback to message parsing (legacy support)
        if not duplicate_uuid:
            # Try to grab the first part after "Duplicate ID collision: "
            # Message format: "Duplicate ID collision: {uuid}. This ID is..."
            try:
                parts = finding.message.split("Duplicate ID collision: ")
                if len(parts) > 1:
                    duplicate_uuid = parts[1].split(".")[0].strip()
            except IndexError:
                pass

        if not duplicate_uuid:
            logger.warning("Could not extract UUID from finding: %s", finding.message)
            continue

        locations = []
        for loc in locations_str.split(", "):
            loc = loc.strip()
            if not loc:
                continue

            try:
                path, line = loc.rsplit(":", 1)
                locations.append((path, int(line)))
            except ValueError:
                logger.warning("Skipping malformed location string: '%s'", loc)
                continue

        if not locations:
            continue

        # Find the original symbol (the one created first)
        original_location = None

        if duplicate_uuid in symbol_creation_dates:
            original_location = locations[0]
        else:
            # Fallback: assume first found is original
            original_location = locations[0]

        logger.info(
            "Duplicate UUID: %s (Original at %s:%s)",
            duplicate_uuid,
            original_location[0],
            original_location[1],
        )

        # Mark all other locations for change
        for path, line_num in locations:
            if (path, line_num) != original_location:
                logger.info("   - Copy found at: %s:%s", path, line_num)
                files_to_modify[path].append((line_num, duplicate_uuid))

    if not files_to_modify:
        logger.info("All duplicates seem to be resolved or are new. No changes needed.")
        return 0

    if dry_run:
        logger.info("-- DRY RUN: No files will be changed. --")
        for path, changes in files_to_modify.items():
            logger.info(
                "  - Would modify %s to fix %d duplicate ID(s).", path, len(changes)
            )
        return len(files_to_modify)

    # Apply the changes
    logger.info("Applying fixes...")
    for file_str, changes in files_to_modify.items():
        file_path = settings.REPO_PATH / file_str
        if not file_path.exists():
            logger.warning("File %s does not exist. Skipping.", file_str)
            continue

        content = file_path.read_text("utf-8")
        lines = content.splitlines()

        for line_num, old_uuid in changes:
            new_uuid = str(uuid.uuid4())
            line_index = line_num - 1

            if 0 <= line_index < len(lines):
                if old_uuid in lines[line_index]:
                    lines[line_index] = lines[line_index].replace(old_uuid, new_uuid)
                    logger.info(
                        "  - Replaced ID in %s:%s -> %s", file_str, line_num, new_uuid
                    )
                else:
                    logger.warning(
                        "  - ID %s not found in %s:%s (line changed?)",
                        old_uuid,
                        file_str,
                        line_num,
                    )
            else:
                logger.warning("  - Line %s out of bounds in %s", line_num, file_str)

        file_path.write_text("\n".join(lines) + "\n", "utf-8")

    return len(files_to_modify)
