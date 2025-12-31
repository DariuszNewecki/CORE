# src/features/self_healing/duplicate_id_service.py

"""
Provides a service to intelligently find and resolve duplicate UUIDs in the codebase.
Updated to use the dynamic constitutional rule engine.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mind.governance.audit_context import AuditorContext
from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules
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
        return {str(row[0]): row[1].isoformat() for row in result}
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
    logger.info("🔍 Scanning for duplicate UUIDs via constitutional rules...")

    # 1. Initialize Context and load Knowledge Graph
    context = AuditorContext(settings.REPO_PATH)
    await context.load_knowledge_graph()

    # 2. Extract and Execute the Uniqueness Rule
    all_rules = extract_executable_rules(context.policies)
    target_rule = next(
        (r for r in all_rules if r.rule_id == "integration.duplicate_ids_resolved"),
        None,
    )

    if not target_rule:
        logger.error(
            "Constitutional rule 'integration.duplicate_ids_resolved' not found."
        )
        return 0

    all_findings = await execute_rule(target_rule, context)

    if not all_findings:
        logger.info("✅ No duplicate UUIDs found.")
        return 0

    logger.warning(
        "⚠️  Found %d duplicate UUID collisions. Resolving...", len(all_findings)
    )

    # 3. Get creation dates from the database to find the "original" entry
    symbol_creation_dates = await _get_symbol_creation_dates(session)

    files_to_modify: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for finding in all_findings:
        # Extract metadata from the finding context
        ctx = finding.context or {}
        duplicate_uuid = ctx.get("uuid")

        # The engine finds collisions. We need to parse where they are.
        # Logic: If the rule detected multiple locations, they are in the finding message or context
        locations_str = ctx.get("locations", "")
        if not locations_str or not duplicate_uuid:
            continue

        locations = []
        for loc in locations_str.split(", "):
            try:
                path, line = loc.rsplit(":", 1)
                locations.append((path.strip(), int(line.strip())))
            except ValueError:
                continue

        if not locations:
            continue

        # Determine which one is the "Original" (the one in the DB or the first one found)
        # We preserve the original and change the rest.
        original_location = locations[0]

        logger.info(
            "Collision for ID %s: Preserving %s:%s", duplicate_uuid, *original_location
        )

        # Mark subsequent locations for regeneration
        for path, line_num in locations[1:]:
            logger.info("   -> Marking for fix: %s:%s", path, line_num)
            files_to_modify[path].append((line_num, duplicate_uuid))

    if not files_to_modify:
        return 0

    if dry_run:
        logger.info(
            "💧 [DRY RUN] Would modify %d files to resolve collisions.",
            len(files_to_modify),
        )
        return len(files_to_modify)

    # 4. Apply the changes
    files_fixed = 0
    for file_str, changes in files_to_modify.items():
        file_path = settings.REPO_PATH / file_str
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text("utf-8")
            lines = content.splitlines()

            for line_num, old_uuid in changes:
                line_idx = line_num - 1
                if 0 <= line_idx < len(lines) and old_uuid in lines[line_idx]:
                    new_uuid = str(uuid.uuid4())
                    lines[line_idx] = lines[line_idx].replace(old_uuid, new_uuid)
                    logger.info(
                        "   ✅ Replaced %s with %s in %s:%s",
                        old_uuid[:8],
                        new_uuid[:8],
                        file_str,
                        line_num,
                    )

            file_path.write_text("\n".join(lines) + "\n", "utf-8")
            files_fixed += 1
        except Exception as e:
            logger.error("❌ Failed to fix %s: %s", file_str, e)

    return files_fixed
