# src/features/maintenance/maintenance_service.py

"""
Provides centralized services for repository maintenance tasks.
CONSTITUTIONAL FIX: Rewire logic now uses FileHandler for governed mutations.
"""

from __future__ import annotations

import re

# CONSTITUTIONAL FIX: Import TYPE_CHECKING
from typing import TYPE_CHECKING

from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.storage.file_handler import FileHandler

logger = getLogger(__name__)

REWIRE_MAP = {
    "system.admin": "cli.commands",
    "system.admin_cli": "cli.admin_cli",
    "agents": "core.agents",
    "system.tools.codegraph_builder": "features.introspection.knowledge_graph_service",
    "system.tools.scaffolder": "features.project_lifecycle.scaffolding_service",
    "shared.services.qdrant_service": "services.clients.qdrant_client",
    "shared.services.embedding_service": "shared.utils.embedding_utils",
    "shared.services.repositories.db.engine": "services.repositories.db.engine",
    "system.governance.models": "shared.models",
}


# ID: 12fcea31-5e2a-46e6-8e8c-9fd529ffc667
def rewire_imports(file_handler: FileHandler, dry_run: bool = True) -> int:
    """
    Scans and corrects Python imports using the governed FileHandler.
    """
    src_dir = settings.REPO_PATH / "src"
    all_python_files = list(src_dir.rglob("*.py"))
    total_changes = 0
    import_re = re.compile("^(from\\s+([a-zA-Z0-9_.]+)|import\\s+([a-zA-Z0-9_.]+))")
    sorted_rewire_keys = sorted(REWIRE_MAP.keys(), key=len, reverse=True)

    for file_path in all_python_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            new_lines = []
            file_changed = False

            for line in lines:
                match = import_re.match(line)
                if not match:
                    new_lines.append(line)
                    continue

                orig_path = match.group(2) or match.group(3)
                modified_line = line
                for old_prefix in sorted_rewire_keys:
                    if orig_path.startswith(old_prefix):
                        new_prefix = REWIRE_MAP[old_prefix]
                        new_import = orig_path.replace(old_prefix, new_prefix, 1)
                        modified_line = line.replace(orig_path, new_import)
                        break

                if modified_line != line:
                    new_lines.append(modified_line)
                    file_changed = True
                    total_changes += 1
                else:
                    new_lines.append(line)

            if file_changed and not dry_run:
                rel_path = str(file_path.relative_to(settings.REPO_PATH))
                # CONSTITUTIONAL FIX: Use governed surface
                file_handler.write_runtime_text(rel_path, "\n".join(new_lines) + "\n")

        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e)

    return total_changes
