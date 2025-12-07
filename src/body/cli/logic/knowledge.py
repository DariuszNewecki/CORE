# src/body/cli/logic/knowledge.py
"""
Implements the logic for knowledge-related CLI commands, such as finding
common, duplicated helper functions across the codebase.
"""

from __future__ import annotations

import asyncio
import logging

from features.self_healing.knowledge_consolidation_service import (
    find_structurally_similar_helpers,
)


logger = logging.getLogger(__name__)


# ID: a4b9c1d8-f3e2-4b1e-a9d5-f8c3d7f4b1e9
def find_common_knowledge(
    min_occurrences: int = 3,
    max_lines: int = 10,
):
    """
    CLI logic to find and display structurally similar helper functions.
    """
    logger.info("Scanning for structurally similar helper functions...")

    duplicates = asyncio.run(
        asyncio.to_thread(find_structurally_similar_helpers, min_occurrences, max_lines)
    )

    if not duplicates:
        logger.info("No common helper functions found meeting the criteria.")
        return duplicates

    logger.info(f"Found {len(duplicates)} cluster(s) of duplicated helper functions.")

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
