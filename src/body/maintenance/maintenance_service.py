# src/body/maintenance/maintenance_service.py

"""
Provides centralized services for repository maintenance tasks.
UPDATED: Hardened for Indented and Prefix-aware re-wiring (Wave 4).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext
    from shared.infrastructure.storage.file_handler import FileHandler

logger = getLogger(__name__)

# THE NEW WORLD MAP
REWIRE_MAP = {
    # Brains (Will)
    "features.autonomy": "will.autonomy",
    "features.self_healing.audit_remediation_service": "will.self_healing.audit_remediation_service",
    "features.self_healing.clarity_service": "will.self_healing.clarity_service",
    "features.self_healing.complexity_service": "will.self_healing.complexity_service",
    "features.test_generation": "will.test_generation",
    # Hands (Body)
    "features.introspection": "body.introspection",
    "features.maintenance": "body.maintenance",
    "features.project_lifecycle": "body.project_lifecycle",
    "features.quality": "body.quality",
    "features.crate_processing": "body.crate_processing",
    "features.operations": "body.operations",
    "features.self_healing": "body.self_healing",
    # Law (Mind)
    "features.governance": "mind.governance",
    # Specific Layer Moves
    "body.cli": "cli",
}


# ID: 12fcea31-5e2a-46e6-8e8c-9fd529ffc667
def rewire_imports(
    context: CoreContext, file_handler: FileHandler, dry_run: bool = True
) -> int:
    """
    Scans and corrects Python imports across the entire src/ directory.

    HARDENED:
    1. Removed '^' anchor to catch indented/lazy imports.
    2. Accounts for 'src.' prefix ghosts.
    3. Prevents self-mutation of the REWIRE_MAP itself.
    """
    src_dir = context.git_service.repo_path / "src"
    all_python_files = list(src_dir.rglob("*.py"))
    total_changes = 0

    # Pattern matches: [optional space] (from|import) [path]
    # Removed ^ to catch lazy imports inside functions/TypeChecking blocks
    import_re = re.compile(r"(\s*(?:from|import)\s+)([a-zA-Z0-9_.]+)")

    sorted_rewire_keys = sorted(REWIRE_MAP.keys(), key=len, reverse=True)

    for file_path in all_python_files:
        # CONSTITUTIONAL GUARD: Don't let the script rewire its own map definition
        if file_path.name == "maintenance_service.py":
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            new_lines = []
            file_changed = False

            for line in lines:
                match = import_re.search(line)
                if not match:
                    new_lines.append(line)
                    continue

                prefix = match.group(1)  # e.g. "    from "
                orig_path = match.group(2)  # e.g. "features.introspection"

                modified_path = orig_path

                # Check for each old path in our map
                for old_key in sorted_rewire_keys:
                    new_val = REWIRE_MAP[old_key]

                    # Handle standard path
                    if modified_path.startswith(old_key):
                        modified_path = modified_path.replace(old_key, new_val, 1)
                        break

                    # Handle the 'src.' ghost prefix
                    src_old_key = f"src.{old_key}"
                    if modified_path.startswith(src_old_key):
                        # We preserve the 'src.' prefix if the project uses absolute roots
                        modified_path = modified_path.replace(
                            src_old_key, f"src.{new_val}", 1
                        )
                        break

                if modified_path != orig_path:
                    # Construct the new line preserving original indentation and keywords
                    new_line = line.replace(orig_path, modified_path, 1)
                    new_lines.append(new_line)
                    file_changed = True
                    total_changes += 1
                else:
                    new_lines.append(line)

            if file_changed and not dry_run:
                rel_path = str(file_path.relative_to(context.git_service.repo_path))
                file_handler.write_runtime_text(rel_path, "\n".join(new_lines) + "\n")

        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e)

    return total_changes
