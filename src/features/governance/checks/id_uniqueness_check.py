# src/features/governance/checks/id_uniqueness_check.py
"""
A constitutional audit check to enforce that every # ID tag is unique across the codebase.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List

from shared.models import AuditFinding, AuditSeverity

from features.governance.checks.base_check import BaseCheck

# Pre-compiled regex for efficiency to find '# ID: <uuid>'
ID_TAG_REGEX = re.compile(
    r"#\s*ID:\s*([0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})"
)


# ID: ddaabb9e-5e9a-4574-b458-dbed610e64e5
class IdUniquenessCheck(BaseCheck):
    """
    Scans the entire source code to ensure that every assigned symbol ID (UUID) is unique.
    This prevents data corruption from accidental copy-paste errors during development.
    """

    # ID: f2a3b4c5-d6e7-f8a9-b0c1-d2e3f4a5b6c7
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check by scanning all Python files in `src/` and returns findings for any duplicate UUIDs.
        """
        # A dictionary to store locations of each UUID: {uuid: [("file/path.py", line_num), ...]}
        uuid_locations: Dict[str, List[tuple[str, int]]] = defaultdict(list)

        src_dir = self.context.repo_path / "src"
        for file_path in src_dir.rglob("*.py"):
            try:
                content = file_path.read_text("utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    match = ID_TAG_REGEX.search(line)
                    if match:
                        found_uuid = match.group(1)
                        rel_path = str(file_path.relative_to(self.context.repo_path))
                        uuid_locations[found_uuid].append((rel_path, i))
            except Exception:
                # Silently ignore files that can't be read or parsed
                continue

        findings = []
        for found_uuid, locations in uuid_locations.items():
            if len(locations) > 1:
                # Found a duplicate!
                locations_str = ", ".join(
                    [f"{path}:{line}" for path, line in locations]
                )
                findings.append(
                    AuditFinding(
                        check_id="linkage.id.duplicate",
                        severity=AuditSeverity.ERROR,
                        message=f"Duplicate ID tag found: {found_uuid}",
                        context={"locations": locations_str},
                    )
                )

        return findings
