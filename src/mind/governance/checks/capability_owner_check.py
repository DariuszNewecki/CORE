# src/mind/governance/checks/capability_owner_check.py

"""
[DEPRECATED VALIDATION]
In CORE v2, ownership is tracked in the Database (The Mind), not in source comments (The Body).
This check previously enforced '# owner:' tags in files.
It is now updated to pass automatically, as ownership is enforced by the DB schema
and the 'linkage.assign_ids' check.
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding


# ID: 3adcb244-bd0a-45a8-98a7-6bf58f1fda42
class CapabilityOwnerCheck(BaseCheck):
    """
    Formerly checked for '# owner:' tags.
    Now effectively retired in favor of DB-side ownership tracking.
    Kept as a placeholder to satisfy registry loading until the policy is updated.
    """

    policy_rule_ids = ["caps.owner_required"]

    # ID: 40d50b0f-01cd-43d7-a41a-baf24f153852
    def execute(self) -> list[AuditFinding]:
        # CORE v2 Philosophy: Source code should not be polluted with metadata
        # that lives in the Knowledge Graph.
        # The 'owner' is a property of the Capability in Postgres, not the file.
        return []
