# src/mind/logic/engines/ast_gate/checks/knowledge_source_check.py

"""
Ensures that operational knowledge SSOT exists in the Database and is usable.

CONSTITUTIONAL COMPLIANCE:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to natively async to eliminate event-loop hijacking.
- Delegates data access to the governance substrate to uphold 'dry_by_design'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from mind.governance.enforcement_methods import (
    AsyncEnforcementMethod,
    KnowledgeSSOTEnforcement,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)

# The policy defines the "Spirit of the Law"
GOVERNANCE_POLICY = Path(".intent/standards/data/governance.json")


# ID: 81d6e8ed-a6f6-444c-acda-9064896c5111
class KnowledgeSourceCheck(RuleEnforcementCheck):
    """
    Orchestrator for Knowledge Source validation.

    This check verifies that the Database contains the required
    operational knowledge (CLI commands, LLM resources, etc.)
    required for CORE to function.
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "db.ssot_for_operational_data",
        "db.cli_registry_in_db",
        "db.llm_resources_in_db",
        "db.cognitive_roles_in_db",
        "db.domains_in_db",
    ]

    policy_file: ClassVar[Path] = GOVERNANCE_POLICY

    # We use the Async enforcement methods defined in the mind.governance home
    enforcement_methods: ClassVar[list[AsyncEnforcementMethod]] = [
        KnowledgeSSOTEnforcement(rule_id="db.ssot_for_operational_data"),
        KnowledgeSSOTEnforcement(rule_id="db.cli_registry_in_db"),
        KnowledgeSSOTEnforcement(rule_id="db.llm_resources_in_db"),
        KnowledgeSSOTEnforcement(rule_id="db.cognitive_roles_in_db"),
        KnowledgeSSOTEnforcement(rule_id="db.domains_in_db"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True

    # ID: bf759401-01f8-41b3-854b-77d20331c002
    async def verify(
        self, context: Any, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        """
        Natively async verification.

        Iterates through the enforcement methods and properly awaits
        database results without hijacking the event loop.
        """
        all_findings: list[AuditFinding] = []

        for method in self.enforcement_methods:
            # We explicitly check for AsyncEnforcementMethod to ensure
            # we are following the 'Architectural Honesty' principle.
            if isinstance(method, AsyncEnforcementMethod):
                # Properly await the DB check
                findings = await method.verify_async(context, rule_data)
                all_findings.extend(findings)
            elif isinstance(method, Any):  # Fallback for sync methods if added later
                findings = method.verify(context, rule_data)
                all_findings.extend(findings)

        return all_findings
