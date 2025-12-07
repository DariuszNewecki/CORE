# src/features/maintenance/maintenance_service.py
"""
Provides centralized services for repository maintenance tasks that were
previously handled by standalone scripts.
"""

from __future__ import annotations

import re

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)

# This map defines the OLD python import paths to the NEW python import paths.
REWIRE_MAP = {
    # Legacy system.admin -> new cli.commands
    "system.admin": "cli.commands",
    "system.admin_cli": "cli.admin_cli",
    # Legacy agents -> new core.agents
    "agents": "core.agents",
    # Legacy system.tools -> new features
    "system.tools.codegraph_builder": "features.introspection.knowledge_graph_service",
    "system.tools.scaffolder": "features.project_lifecycle.scaffolding_service",
    # Legacy shared locations
    "shared.services.qdrant_service": "services.clients.qdrant_client",
    "shared.services.embedding_service": "services.adapters.embedding_provider",
    "shared.services.repositories.db.engine": "services.repositories.db.engine",
    "system.governance.models": "shared.models",
}


# ID: 76ae8501-8f82-4a13-9648-bf1af142aae3
def rewire_imports(dry_run: bool = True) -> int:
    """
    Scans the entire 'src' directory and corrects Python import statements
    based on the architectural REWIRE_MAP. This is a critical tool for use
    after major refactoring.

    Args:
        dry_run: If True, only prints changes without writing them.

    Returns:
        The number of import changes made or proposed.
    """
    src_dir = settings.REPO_PATH / "src"
    all_python_files = list(src_dir.rglob("*.py"))
    total_changes = 0
    import_re = re.compile(r"^(from\s+([a-zA-Z0-9_.]+)|import\s+([a-zA-Z0-9_.]+))")

    # Sort keys by length, longest first, to handle nested paths correctly
    sorted_rewire_keys = sorted(REWIRE_MAP.keys(), key=len, reverse=True)

    for file_path in all_python_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            new_lines = []
            file_was_changed = False

            for line in lines:
                match = import_re.match(line)
                if not match:
                    new_lines.append(line)
                    continue

                original_import_path = match.group(2) or match.group(3)
                modified_line = line

                for old_prefix in sorted_rewire_keys:
                    if original_import_path.startswith(old_prefix):
                        new_prefix = REWIRE_MAP[old_prefix]
                        new_import_path = original_import_path.replace(
                            old_prefix, new_prefix, 1
                        )
                        modified_line = line.replace(
                            original_import_path, new_import_path
                        )
                        break  # Stop after the first (longest) match

                if modified_line != line:
                    logger.info(
                        f"Change detected in: {file_path.relative_to(settings.REPO_PATH)}"
                    )
                    logger.info("  - %s", line)
                    logger.info("  + %s", modified_line)
                    new_lines.append(modified_line)
                    file_was_changed = True
                    total_changes += 1
                else:
                    new_lines.append(line)

            if file_was_changed and not dry_run:
                file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        except Exception as e:
            logger.error("Error processing {file_path}: %s", e)

    return total_changes
