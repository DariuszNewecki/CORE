# src/mind/governance/checks/id_uniqueness_check.py
"""
Enforces linkage.duplicate_ids: Every # ID tag must be unique across the codebase.
Prevents identity collisions that corrupt the Knowledge Graph.
"""

from __future__ import annotations

import re
from collections import defaultdict

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# Pre-compiled regex for efficiency to find '# ID: <uuid>'
ID_TAG_REGEX = re.compile(
    r"#\s*ID:\s*([0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})"
)


# ID: ddaabb9e-5e9a-4574-b458-dbed610e64e5
class IdUniquenessCheck(BaseCheck):
    """
    Scans the entire source code to ensure that every assigned symbol ID (UUID) is unique.
    Ref: standard_operations_general (linkage.duplicate_ids)
    """

    policy_rule_ids = ["linkage.duplicate_ids"]

    # ID: f2a3b4c5-d6e7-f8a9-b0c1-d2e3f4a5b6c7
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by scanning all Python files in `src/`.
        Returns findings for EVERY occurrence of a duplicate UUID.
        """
        # Store locations: {uuid: [("file/path.py", line_num), ...]}
        uuid_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)

        # 1. Scan Phase
        for file_path in self.src_dir.rglob("*.py"):
            try:
                rel_path = str(file_path.relative_to(self.repo_root))
                content = file_path.read_text(encoding="utf-8")

                for i, line in enumerate(content.splitlines(), 1):
                    # Optimization: Skip lines that don't look like comments/IDs
                    if "#" not in line:
                        continue

                    match = ID_TAG_REGEX.search(line)
                    if match:
                        found_uuid = match.group(1)
                        uuid_locations[found_uuid].append((rel_path, i))

            except Exception as e:
                logger.debug("Failed to scan %s for IDs: %s", file_path, e)
                continue

        # 2. Reporting Phase
        findings = []
        for found_uuid, locations in uuid_locations.items():
            if len(locations) > 1:
                # Collision detected! Report finding for EACH location
                # so it shows up in code reviews/IDE for all affected files.

                locations_fmt = [f"{path}:{line_num}" for path, line_num in locations]

                for file_path, line_num in locations:
                    # Identify 'other' locations to help the user resolve it
                    others = [
                        loc
                        for loc in locations_fmt
                        if not loc.startswith(f"{file_path}:{line_num}")
                    ]

                    findings.append(
                        AuditFinding(
                            check_id="linkage.duplicate_ids",
                            severity=AuditSeverity.ERROR,
                            message=(
                                f"Duplicate ID collision: {found_uuid}. "
                                f"This ID is also used in: {', '.join(others)}. "
                                "Run `core-admin fix duplicate-ids`."
                            ),
                            file_path=file_path,
                            line_number=line_num,
                            context={"uuid": found_uuid, "collision_peers": others},
                        )
                    )

        return findings
