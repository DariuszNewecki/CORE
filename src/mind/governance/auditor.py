# src/mind/governance/auditor.py
# ID: 85bb69ce-b22a-490a-8a1d-92a5da7e2646
"""Constitutional Auditor - The Unified Enforcement Engine.

PURIFIED (V2.3.0)
- Removed FileService and service_registry to satisfy Mind/Body separation.
- Returns data structures only; does not perform filesystem mutations.
- Caller is responsible for artifact persistence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mind.governance.constitutional_auditor_dynamic import (
    get_dynamic_execution_stats,
    run_dynamic_rules,
)
from mind.logic.engines.registry import EngineRegistry
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: 153b13ec-7bc5-4598-bcae-1b5ba5f03eca
class ConstitutionalAuditor:
    """Evaluates system compliance by executing dynamic rules via engines.

    Returns structured data for the Body layer to report or persist.
    """

    def __init__(self, context: AuditorContext):
        self.context = context

    # ID: e70bf756-620a-4065-99df-34b03cc25c96
    async def run_full_audit_async(self) -> dict:
        """Execute the full constitutional audit and return results + stats.

        Returns:
            dict: {
                "findings": list[AuditFinding],
                "stats": dict,
                "executed_rule_ids": set[str],
                "passed": bool,
            }
        """
        await self.context.load_knowledge_graph()

        executed_rule_ids: set[str] = set()

        # NOTE: db_session is assumed to be provided via context
        # (JIT injected by the CLI or Service Registry before call)
        EngineRegistry.initialize(self.context.paths)

        findings: list[AuditFinding] = await run_dynamic_rules(
            self.context,
            executed_rule_ids=executed_rule_ids,
        )

        # Calculate statistics
        stats = get_dynamic_execution_stats(self.context, executed_rule_ids)

        # Determine pass/fail based on blocking errors
        passed = not any(
            (f.severity if hasattr(f, "severity") else AuditSeverity.INFO)
            == AuditSeverity.ERROR
            for f in findings
        )

        return {
            "findings": findings,
            "stats": stats,
            "executed_rule_ids": executed_rule_ids,
            "passed": passed,
        }
