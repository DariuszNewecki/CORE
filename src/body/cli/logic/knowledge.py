# src/body/cli/logic/knowledge.py

"""
Implements the logic for knowledge-related CLI commands, such as finding
common, duplicated helper functions across the codebase.
"""

from __future__ import annotations

import asyncio
import logging

from body.self_healing.knowledge_consolidation_service import (
    find_structurally_similar_helpers,
)
from shared.logger import getLogger


logger = getLogger(__name__)
logger = logging.getLogger(__name__)


# ID: ebecf29a-8a1a-41f4-b416-44d5df33a918
async def find_common_knowledge(min_occurrences: int = 3, max_lines: int = 10):
    """
    CLI logic to find and display structurally similar helper functions.
    """
    logger.info("Scanning for structurally similar helper functions...")
    duplicates = await asyncio.to_thread(
        find_structurally_similar_helpers, min_occurrences, max_lines
    )
    if not duplicates:
        logger.info("No common helper functions found meeting the criteria.")
        return duplicates
    logger.info("Found %s cluster(s) of duplicated helper functions.", len(duplicates))
    result = {}
    for i, (hash_val, locations) in enumerate(duplicates.items(), 1):
        cluster_info = {
            "hash": hash_val,
            "count": len(locations),
            "locations": sorted(locations),
        }
        result[f"cluster_{i}"] = cluster_info
    logger.info(
        "Use these findings to refactor and consolidate helpers into `src/shared/utils/` to uphold the `dry_by_design` principle."
    )
    return result
