# src/mind/governance/checks/id_uniqueness_check.py
"""
Enforces linkage.duplicate_ids: Every # ID tag must be unique across the codebase.
Prevents identity collisions that corrupt the Knowledge Graph.

Ref: .intent/charter/standards/operations/operations.json
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

OPERATIONS_POLICY = Path(".intent/charter/standards/operations/operations.json")

# Pre-compiled regex for efficiency to find '# ID: <uuid>'
ID_TAG_REGEX = re.compile(
    r"#\s*ID:\s*([0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})"
)


# ID: id-uniqueness-enforcement
# ID: b84a4189-7877-42ec-96f4-7628a5c47f7b
class IdUniquenessEnforcement(EnforcementMethod):
    """
    Scans the entire source code to ensure that every assigned symbol ID (UUID) is unique.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: df830ad4-3bfe-481a-9230-42e247cb4a10
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        """
        Runs the check by scanning all Python files in `src/`.
        Returns findings for EVERY occurrence of a duplicate UUID.
        """
        # Store locations: {uuid: [("file/path.py", line_num), ...]}
        uuid_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)

        # 1. Scan Phase
        for file_path in context.src_dir.rglob("*.py"):
            try:
                rel_path = str(file_path.relative_to(context.repo_path))
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

                locations_fmt = [f"{path}:{line_num}" for path, line_num in locations]
                all_locations_str = ", ".join(locations_fmt)

                for file_path, line_num in locations:
                    # Identify 'other' locations to help the user resolve it
                    others = [
                        loc
                        for loc in locations_fmt
                        if not loc.startswith(f"{file_path}:{line_num}")
                    ]

                    findings.append(
                        AuditFinding(
                            check_id=self.rule_id,
                            severity=self.severity,
                            message=(
                                f"Duplicate ID collision: {found_uuid}. "
                                f"This ID is also used in: {', '.join(others)}. "
                                "Run `core-admin fix duplicate-ids`."
                            ),
                            file_path=file_path,
                            line_number=line_num,
                            context={
                                "uuid": found_uuid,
                                "collision_peers": others,
                                "locations": all_locations_str,
                            },
                        )
                    )

        return findings


# ID: ddaabb9e-5e9a-4574-b458-dbed610e64e5
class IdUniquenessCheck(RuleEnforcementCheck):
    """
    Scans the entire source code to ensure that every assigned symbol ID (UUID) is unique.

    Ref: .intent/charter/standards/operations/operations.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["linkage.duplicate_ids"]

    policy_file: ClassVar[Path] = OPERATIONS_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IdUniquenessEnforcement(rule_id="linkage.duplicate_ids"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
