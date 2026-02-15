# src/body/maintenance/maintenance_service.py

"""
Provides centralized services for repository maintenance tasks.
UPDATED: Map adjusted for layered architecture (Wave 4 Re-wiring).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.storage.file_handler import FileHandler

logger = getLogger(__name__)

# THE NEW WORLD MAP
# This tells the tool: "If you see the old name on the left, change it to the name on the right."
REWIRE_MAP = {
    # Old Feature paths -> New Will paths (The Brains)
    "features.autonomy": "will.autonomy",
    "features.self_healing.audit_remediation_service": "will.self_healing.audit_remediation_service",
    "features.self_healing.clarity_service": "will.self_healing.clarity_service",
    "features.self_healing.complexity_service": "will.self_healing.complexity_service",
    "features.test_generation": "will.test_generation",
    # Old Feature paths -> New Body paths (The Hands)
    "features.introspection": "body.introspection",
    "features.maintenance": "body.maintenance",
    "features.project_lifecycle": "body.project_lifecycle",
    "features.quality": "body.quality",
    "features.crate_processing": "body.crate_processing",
    "features.operations": "body.operations",
    "features.self_healing": "body.self_healing",  # Catch-all for deterministic services
    # Old Feature paths -> New Mind paths (The Law)
    "features.governance": "mind.governance",
}


# ID: 12fcea31-5e2a-46e6-8e8c-9fd529ffc667
def rewire_imports(file_handler: FileHandler, dry_run: bool = True) -> int:
    """
    Scans and corrects Python imports across the entire src/ directory.
    """
    src_dir = settings.REPO_PATH / "src"
    all_python_files = list(src_dir.rglob("*.py"))
    total_changes = 0

    # Matches 'from features.X' or 'import features.X'
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
                file_handler.write_runtime_text(rel_path, "\n".join(new_lines) + "\n")

        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e)

    return total_changes
