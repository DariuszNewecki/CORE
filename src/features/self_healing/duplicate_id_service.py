# src/features/self_healing/duplicate_id_service.py
# ID: 5891cbbe-ae62-4743-92fa-2e204ca5fa13

"""
Provides a service to intelligently find and resolve duplicate UUIDs in the codebase.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.atomic.executor import ActionExecutor
from mind.governance.audit_context import AuditorContext
from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules
from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


async def _get_symbol_creation_dates(session: AsyncSession) -> dict[str, str]:
    """
    Queries the database to get the creation timestamp for each symbol UUID.
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
async def resolve_duplicate_ids(
    context: CoreContext, session: AsyncSession, dry_run: bool = True
) -> int:
    """
    Finds all duplicate IDs and fixes them via the ActionExecutor Gateway.

    Args:
        context: CoreContext (Required for ActionExecutor)
        session: Database session
        dry_run: If True, only report (write=False in Gateway)

    Returns:
        The number of files that were (or would be) modified.
    """
    logger.info("🔍 Scanning for duplicate UUIDs via constitutional rules...")

    # 1. Initialize Gateway and Context
    executor = ActionExecutor(context)
    auditor_context = AuditorContext(settings.REPO_PATH)
    await auditor_context.load_knowledge_graph()

    # 2. Extract and Execute the Uniqueness Rule
    all_rules = extract_executable_rules(auditor_context.policies)
    target_rule = next(
        (r for r in all_rules if r.rule_id == "integration.duplicate_ids_resolved"),
        None,
    )

    if not target_rule:
        logger.error(
            "Constitutional rule 'integration.duplicate_ids_resolved' not found."
        )
        return 0

    all_findings = await execute_rule(target_rule, auditor_context)

    if not all_findings:
        logger.info("✅ No duplicate UUIDs found.")
        return 0

    logger.warning(
        "⚠️  Found %d duplicate UUID collisions. Resolving...", len(all_findings)
    )

    # 3. Analyze collisions
    files_to_modify: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for finding in all_findings:
        ctx = finding.context or {}
        duplicate_uuid = ctx.get("uuid")
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

        # Preserving the first found location (Original)
        original_location = locations[0]
        logger.info(
            "Collision for ID %s: Preserving %s:%s", duplicate_uuid, *original_location
        )

        # Mark subsequent locations for regeneration
        for path, line_num in locations[1:]:
            files_to_modify[path].append((line_num, duplicate_uuid))

    if not files_to_modify:
        return 0

    # 4. Apply changes via Governed Gateway
    files_fixed = 0
    write_mode = not dry_run

    for file_str, changes in files_to_modify.items():
        file_path = settings.REPO_PATH / file_str
        if not file_path.exists():
            continue

        try:
            # We read the file to prepare the new content
            content = file_path.read_text("utf-8")
            lines = content.splitlines()

            for line_num, old_uuid in changes:
                line_idx = line_num - 1
                if 0 <= line_idx < len(lines) and old_uuid in lines[line_idx]:
                    new_uuid = str(uuid.uuid4())
                    lines[line_idx] = lines[line_idx].replace(old_uuid, new_uuid)
                    logger.debug(
                        "   -> Prepared fix: %s -> %s in %s:%s",
                        old_uuid[:8],
                        new_uuid[:8],
                        file_str,
                        line_num,
                    )

            # CONSTITUTIONAL GATEWAY: Instead of writing directly, we use the executor.
            # This ensures IntentGuard is checked and the action is logged to DB.
            result = await executor.execute(
                action_id="file.edit",
                write=write_mode,
                file_path=file_str,
                code="\n".join(lines) + "\n",
            )

            if result.ok:
                files_fixed += 1
            else:
                logger.error(
                    "❌ Gateway blocked fix for %s: %s",
                    file_str,
                    result.data.get("error"),
                )

        except Exception as e:
            logger.error("❌ Unexpected error preparing fix for %s: %s", file_str, e)

    return files_fixed
