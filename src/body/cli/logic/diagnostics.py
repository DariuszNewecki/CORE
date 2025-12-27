# src/body/cli/logic/diagnostics.py
"""
Logic layer for CLI diagnostics commands.
All presentation logic (console, Rich UI, etc.) lives in body.cli.commands.inspect.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.config import settings
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e9d2a1f3-5c4b-8a7e-9f1d-2b3c4d5e6f7a
async def get_unassigned_symbols_logic() -> list[dict[str, Any]]:
    """
    Get symbols that have not been assigned a capability ID.

    NOTE: This function is now a lightweight wrapper that queries the knowledge graph directly.
    The old audit_unassigned_capabilities module has been deprecated in favor of
    constitutional policy enforcement via .intent/policies/code/linkage_standards.json
    """
    try:
        knowledge_service = KnowledgeService(settings.REPO_PATH)
        graph = await knowledge_service.get_graph()
        symbols = graph.get("symbols", {})

        unassigned = []
        for key, symbol_data in symbols.items():
            name = symbol_data.get("name")
            if name is None:
                continue

            # Skip private symbols
            is_public = not name.startswith("_")

            # Skip test files (constitutional exclusion)
            file_path = symbol_data.get("file_path", "")
            if "tests/" in file_path or "/test" in file_path:
                continue

            # Check if unassigned
            is_unassigned = symbol_data.get("capability") == "unassigned"

            if is_public and is_unassigned:
                symbol_data["key"] = key
                unassigned.append(symbol_data)

        return unassigned
    except Exception as e:
        logger.error("Error processing knowledge graph: %s", e)
        return []


# ID: 53145751-6d32-41e8-a424-3829d05f8237
def get_all_constitutional_paths(
    meta_config: dict[str, Any], mind_path: Path
) -> set[Path]:
    """Returns all paths that the constitution considers governance-critical."""
    required = set()

    # Core constitutional directories
    for dir_key in ["intent_root", "policies_dir", "schemas_dir"]:
        if dir_val := meta_config.get(dir_key):
            p = mind_path / dir_val
            if p.exists():
                required.add(p)

    return required


# ID: 5086836c-c833-4099-a6da-2522eda85ec3
def list_constitutional_files_logic() -> list[str]:
    """
    Returns the list of constitutional files according to meta.yaml.
    """
    logger.info("Getting auditor's interpretation of meta.yaml...")
    required_paths = get_all_constitutional_paths(settings._meta_config, settings.MIND)
    return sorted(list(str(p) for p in required_paths))
