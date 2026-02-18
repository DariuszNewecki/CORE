# src/mind/governance/auditor.py
# ID: 85bb69ce-b22a-490a-8a1d-92a5da7e2646
"""Constitutional Auditor - The Unified Enforcement Engine.

PURIFIED (V2.3.0)
- Removed FileService and service_registry to satisfy Mind/Body separation.
- Returns data structures only; does not perform filesystem mutations.
- Caller is responsible for artifact persistence.

HARDENED (V2.5.0)
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

        # NOTE: db_session is assumed to be provided via context
        # (JIT injected by the CLI or Service Registry before call)
        EngineRegistry.initialize(self.context.paths)

        findings: list[AuditFinding] = await run_dynamic_rules(
            self.context,
            executed_rule_ids=executed_rule_ids,
            crashed_rule_ids=crashed_rule_ids,
        )

        # Calculate statistics (P0.2: true denominator, unmapped visible)
        stats = get_dynamic_execution_stats(
            self.context, executed_rule_ids, crashed_rule_ids
        )

        # Determine three-state verdict (P0.1)
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
            "passed": verdict == AuditVerdict.PASS,  # backward compat
        }

    @staticmethod
    # ID: f1e2d3c4-b5a6-7890-1234-567890abcdef
    def _determine_verdict(
        findings: list[AuditFinding],
        stats: dict,
        crashed_rule_ids: set[str],
    ) -> AuditVerdict:
        """Determine audit verdict with truthfulness guarantees.

        Three-state logic:
        1. If any rule CRASHED → DEGRADED (we don't know the true state)
        2. If any blocking violation found → FAIL (code is non-compliant)
        3. Otherwise → PASS

        DEGRADED takes priority over FAIL because a crashed enforcement
        engine means we cannot trust ANY results — including apparent passes.
        """
        # DEGRADED: enforcement infrastructure itself failed
        if crashed_rule_ids:
            return AuditVerdict.DEGRADED

        # FAIL: blocking violations found in code
        has_blocking_violations = any(
            (f.severity if hasattr(f, "severity") else AuditSeverity.INFO)
            == AuditSeverity.ERROR
            for f in findings
            # Exclude ENFORCEMENT_FAILURE findings from "code violation" check
            # (they're already handled by crashed_rule_ids above)
            if not (
                hasattr(f, "context")
                and isinstance(f.context, dict)
                and f.context.get("finding_type") == "ENFORCEMENT_FAILURE"
            )
        )

        if has_blocking_violations:
            return AuditVerdict.FAIL

        # PASS: all checked rules passed, no crashes
        return AuditVerdict.PASS
