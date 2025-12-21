# src/mind/governance/checks/integration_duplicate_ids_check.py
"""
Enforces integration.duplicate_ids_resolved: No duplicate ID tags before integration.

Verifies:
- integration.duplicate_ids_resolved - Duplicate '# ID:' tags must be resolved

Ref: .intent/charter/standards/operations/operations.json
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: duplicate-ids-enforcement
# ID: c1d2e3f4-a5b6-7c8d-9e0f-1a2b3c4d5e6f
class DuplicateIdsEnforcement(EnforcementMethod):
    """
    Scans all Python files for duplicate '# ID:' tags.

    Each UUID must be unique across the entire codebase. Duplicates indicate
    copy-paste errors or merge conflicts that must be resolved before integration.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: f9e8d7c6-b5a4-3c2b-1d0e-9f8e7d6c5b4a
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # Track all ID occurrences: id -> list of (file_path, line_number)
        id_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)

        for file_path in context.python_files:
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
                rel_path = str(file_path.relative_to(context.repo_path))

                for i, line in enumerate(lines, 1):
                    stripped = line.strip()

                    # Match both "# ID:" and "#ID:" patterns
                    if stripped.startswith("# ID:") or stripped.startswith("#ID:"):
                        # Extract the UUID
                        if "# ID:" in stripped:
                            uuid_part = stripped.split("# ID:", 1)[1].strip()
                        else:
                            uuid_part = stripped.split("#ID:", 1)[1].strip()

                        # Clean up any trailing comments
                        uuid_str = uuid_part.split()[0] if uuid_part else ""

                        if uuid_str:
                            id_locations[uuid_str].append((rel_path, i))

            except Exception as e:
                logger.debug("Failed to scan %s for duplicate IDs: %s", file_path, e)
                continue

        # Find duplicates
        for uuid_str, locations in id_locations.items():
            if len(locations) > 1:
                # Format locations for the finding message
                location_strs = [f"{path}:{line}" for path, line in locations]
                locations_summary = ", ".join(location_strs[:5])  # Show first 5
                if len(locations) > 5:
                    locations_summary += f", ... ({len(locations) - 5} more)"

                # Report on the first occurrence (arbitrary choice)
                first_path, first_line = locations[0]

                findings.append(
                    self._create_finding(
                        message=(
                            f"Duplicate ID '{uuid_str}' found in {len(locations)} locations: "
                            f"{locations_summary}. Run 'core-admin fix duplicate-ids --write' to resolve."
                        ),
                        file_path=first_path,
                        line_number=first_line,
                    )
                )

        if findings:
            logger.warning(
                "Found %d duplicate ID(s). Integration blocked until resolved.",
                len(findings),
            )

        return findings


# ID: e2f3a4b5-c6d7-8e9f-0a1b-2c3d4e5f6a7b
class IntegrationDuplicateIdsCheck(RuleEnforcementCheck):
    """
    Enforces integration.duplicate_ids_resolved before integration.

    Ref: .intent/charter/standards/operations/operations.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["integration.duplicate_ids_resolved"]

    policy_file: ClassVar = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        DuplicateIdsEnforcement(
            rule_id="integration.duplicate_ids_resolved",
            severity=AuditSeverity.ERROR,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
