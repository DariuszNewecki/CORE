# src/body/cli/logic/diagnostics.py

"""
src/body/cli/logic/diagnostics.py

Diagnostic Logic Module.
Compliance:
- body_contracts.yaml: Headless (no print/rich), returns data/ActionResults.
- layer_contracts.yaml: Pure logic layer.
"""

from __future__ import annotations

from typing import Any

import typer

from features.introspection.audit_unassigned_capabilities import get_unassigned_symbols
from features.introspection.graph_analysis_service import find_semantic_clusters
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.utils.constitutional_parser import get_all_constitutional_paths


logger = getLogger(__name__)


# ID: 3777d2b8-ee32-4bd7-b4ba-499999b2e0c0
async def find_clusters_logic(
    context: CoreContext, n_clusters: int
) -> list[dict[str, Any]]:
    """
    Logic for finding semantic clusters.
    Returns list of clusters or empty list.
    """
    logger.info("Finding semantic clusters with n_clusters=%s...", n_clusters)

    # Lazy load Qdrant service if missing
    if context.qdrant_service is None and context.registry:
        try:
            context.qdrant_service = await context.registry.get_qdrant_service()
        except Exception as e:
            logger.error("Failed to initialize QdrantService: %s", e)
            return []

    clusters = await find_semantic_clusters(
        qdrant_service=context.qdrant_service, n_clusters=n_clusters
    )

    if not clusters:
        logger.warning("No clusters found.")
        return []

    logger.info("Found %s clusters.", len(clusters))
    return clusters


# ID: 1e0e30f7-9ea5-4fa7-a506-569db41dd9bf
def build_cli_tree_data(typer_app: typer.Typer) -> list[dict[str, Any]]:
    """
    Recursively builds a dictionary representation of the CLI command tree.
    Pure data transformation.
    """
    structure = []

    # Process Commands
    # Accessing internal typer structures to build the tree
    for cmd_info in sorted(typer_app.registered_commands, key=lambda c: c.name or ""):
        if not cmd_info.name:
            continue
        help_text = cmd_info.help.split("\n")[0] if cmd_info.help else ""
        structure.append({"type": "command", "name": cmd_info.name, "help": help_text})

    # Process Groups (Recursive)
    for group_info in sorted(typer_app.registered_groups, key=lambda g: g.name or ""):
        if not group_info.name:
            continue

        # Typer stores help in the inner info object
        help_text = (
            group_info.typer_instance.info.help.split("\n")[0]
            if group_info.typer_instance.info.help
            else ""
        )

        structure.append(
            {
                "type": "group",
                "name": group_info.name,
                "help": help_text,
                "children": build_cli_tree_data(group_info.typer_instance),
            }
        )

    return structure


# ID: 07722b2e-1bbd-4d01-a2d0-28bafe7e2fe2
def get_meta_paths_logic() -> list[str]:
    """Returns sorted list of all constitutional file paths."""
    logger.info("Getting auditor's interpretation of meta.yaml...")
    required_paths = get_all_constitutional_paths(settings._meta_config, settings.MIND)
    return sorted(list(required_paths))


# ID: 1fcd332c-7f52-4236-9ef1-dafc08cda8bc
def get_unassigned_symbols_logic() -> list[dict[str, Any]]:
    """Wrapper for unassigned symbol logic."""
    return get_unassigned_symbols()
