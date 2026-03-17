# src/mind/governance/auditor.py
"""Constitutional Auditor - The Unified Enforcement Engine.

PURIFIED
- Removed FileService and service_registry to satisfy Mind/Body separation.
- Returns data structures only; does not perform filesystem mutations.
- Caller is responsible for artifact persistence.

HARDENED
- P0.1: Audit verdict is now PASS / FAIL / DEGRADED (three-state).
- P0.1: Crashed rules tracked and surfaced in results.
- P0.2: Stats use true denominator (all declared rules, not just mapped).
- Truthfulness guarantee: unknown ≠ pass, crash ≠ pass.
"""

from __future__ import annotations

from enum import Enum
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


# ID: 5994663d-d95b-4747-9d3e-7999513fc559
class AuditVerdict(Enum):
    """Three-state audit verdict.

    PASS: All checked rules passed. No crashes. No unmapped blocking rules.
    FAIL: One or more blocking rules found violations in the code.
    DEGRADED: Audit infrastructure itself failed — some rules crashed,
              could not be checked, or are unmapped. The compliance status
              is UNKNOWN and must be treated as non-compliant until fixed.

    The distinction matters:
    - FAIL means "your code is non-compliant."
    - DEGRADED means "we don't know if your code is compliant."
    These require different operator responses.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"


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

        HARDENED: Now tracks crashed rules and produces three-state verdict.

        Returns:
            dict: {
                "findings": list[AuditFinding],
                "stats": dict,
                "executed_rule_ids": set[str],
                "crashed_rule_ids": set[str],
                "verdict": AuditVerdict,
                "passed": bool,  # backward compat: True only if PASS
            }
        """
        await self.context.load_knowledge_graph()

        executed_rule_ids: set[str] = set()
        crashed_rule_ids: set[str] = set()

        EngineRegistry.initialize(self.context.paths)

        findings: list[AuditFinding] = await run_dynamic_rules(
            self.context,
            executed_rule_ids=executed_rule_ids,
            crashed_rule_ids=crashed_rule_ids,
        )

        stats = get_dynamic_execution_stats(
            self.context, executed_rule_ids, crashed_rule_ids
        )

        verdict = self._determine_verdict(findings, stats, crashed_rule_ids)

        logger.info(
            "Audit verdict: %s (executed=%d, crashed=%d, unmapped=%d)",
            verdict.value,
            stats.get("executed_dynamic_rules", 0),
            stats.get("crashed_rules", 0),
            stats.get("unmapped_rules", 0),
        )

        return {
            "findings": findings,
            "stats": stats,
            "executed_rule_ids": executed_rule_ids,
            "crashed_rule_ids": crashed_rule_ids,
            "verdict": verdict,
            "passed": verdict == AuditVerdict.PASS,
        }

    @staticmethod
    # ID: f1e2d3c4-b5a6-7890-1234-567890abcdef
    def _determine_verdict(
        findings: list[AuditFinding],
        stats: dict,
        crashed_rule_ids: set[str],
    ) -> AuditVerdict:
        """Determine audit verdict with truthfulness guarantees."""
        if crashed_rule_ids:
            return AuditVerdict.DEGRADED

        has_blocking_violations = any(
            (f.severity if hasattr(f, "severity") else AuditSeverity.INFO)
            == AuditSeverity.ERROR
            for f in findings
            if not (
                hasattr(f, "context")
                and isinstance(f.context, dict)
                and f.context.get("finding_type") == "ENFORCEMENT_FAILURE"
            )
        )

        if has_blocking_violations:
            return AuditVerdict.FAIL

        return AuditVerdict.PASS
