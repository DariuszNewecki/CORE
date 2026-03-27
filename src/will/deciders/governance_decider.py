# src/will/deciders/governance_decider.py
"""
Governance Decider — DECIDE phase component.

The final gatekeeper that authorizes or blocks state-changing execution.

Constitutional change (Logic Conservation Gate promotion):
    GovernanceDecider now recognises ComponentResults from
    LogicConservationValidator specifically. A logic evaporation verdict
    is treated as a CRITICAL blocker regardless of risk tier — it cannot
    be overridden by confidence thresholds or tier relaxation.

    This makes the Anti-Lobotomy gate constitutional rather than local
    to ComplexityRemediationService. Any workflow that routes through
    GovernanceDecider receives the protection automatically.

Constitutional alignment:
- Layer:     will — decision-making, never execution
- Phase:     RUNTIME — authorises or blocks before any state change
- Authority: constitution — logic conservation blocks at all tiers
- Boundary:  no get_session, no file writes, no Body implementation

LAYER: will/deciders — RUNTIME phase decision component. Aggregates
evaluator evidence and produces a formal Go/No-Go authorisation token.
"""

from __future__ import annotations

import time
from typing import Any

from shared.component_primitive import ComponentResult
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer
from will.strategists.base_strategist import BaseStrategist


logger = getLogger(__name__)

# Component ID of the logic conservation gate — used to detect its results
# without creating a hard import dependency on the Body layer validator.
_LOGIC_CONSERVATION_COMPONENT_ID = "logic_conservation_validator"

# Verdict key written by LogicConservationValidator on evaporation
_EVAPORATION_VERDICT = "logic_evaporation"


# ID: 79a654be-b451-4932-93fe-d90b4a8f7a77
class GovernanceDecider(BaseStrategist):
    """
    Evaluates cumulative evidence to authorise execution.

    Responsibilities:
    - Aggregate results from multiple Evaluators.
    - Detect CRITICAL violations (logic evaporation, layer breaches).
    - Check for any 'not ok' results from required Evaluators.
    - Evaluate whether confidence meets the threshold for the Risk Tier.
    - Produce a formal 'Authorization Token' or 'Halt' signal.

    Logic Conservation Gate:
        Results from LogicConservationValidator are treated as CRITICAL
        blockers. A logic_evaporation verdict halts execution regardless
        of risk tier, confidence level, or other passing evaluations.
        This cannot be overridden at the Decider level — it requires an
        explicit deletions_authorized=True flag upstream in the workflow.
    """

    def __init__(self) -> None:
        self.tracer = DecisionTracer()

    # ID: c2aeb827-6b0d-4036-8fca-a01fc2244524
    async def execute(
        self,
        evaluation_results: list[ComponentResult],
        risk_tier: str = "STANDARD",
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Make a final Go/No-Go decision.

        Args:
            evaluation_results: Ordered list of ComponentResults from evaluators.
                                 Must include LogicConservationValidator result
                                 for any workflow that modifies source files.
            risk_tier:          ROUTINE | STANDARD | ELEVATED | CRITICAL.
                                 Higher tiers require higher average confidence.

        Returns:
            ComponentResult where:
                data["can_proceed"] = True  → execution is authorised
                data["can_proceed"] = False → execution is blocked
                data["blockers"]            → list of reasons for halt
                data["authorization_token"] → opaque token if authorised
        """
        start_time = time.time()

        violations: list[str] = []
        warnings: list[str] = []
        critical_blocks: list[str] = []
        total_confidence = 0.0

        # ── 1. Aggregate Evidence ─────────────────────────────────────────────
        for res in evaluation_results:
            # CRITICAL path: Logic Conservation Gate.
            # A logic_evaporation verdict is a hard constitutional block.
            # It bypasses the normal violation aggregation and fires immediately.
            if res.component_id == _LOGIC_CONSERVATION_COMPONENT_ID:
                if not res.ok and res.data.get("verdict") == _EVAPORATION_VERDICT:
                    msg = (
                        f"CRITICAL — Logic evaporation detected by "
                        f"{_LOGIC_CONSERVATION_COMPONENT_ID}: "
                        f"{res.data.get('message', 'proposed code below mass threshold')}"
                    )
                    critical_blocks.append(msg)
                    logger.error("GovernanceDecider: %s", msg)
                # Whether ok or not, still accumulate confidence normally.

            # Standard violation path: any not-ok evaluator blocks execution.
            if not res.ok:
                violations.append(
                    f"{res.component_id}: {res.data.get('error', res.data.get('message', 'Unknown failure'))}"
                )

            # Collect warnings from evaluator metadata.
            violation_count = res.metadata.get("violation_count", 0)
            if violation_count > 0:
                warnings.append(
                    f"{res.component_id} reported {violation_count} issue(s)."
                )

            total_confidence += res.confidence

        avg_confidence = (
            total_confidence / len(evaluation_results) if evaluation_results else 1.0
        )

        # ── 2. Decision Logic (The Law) ───────────────────────────────────────

        # Rule A: Critical constitutional blocks always halt — no tier override.
        if critical_blocks:
            can_proceed = False
            all_blockers = critical_blocks + violations
            decision = "HALT"
            logger.warning(
                "GovernanceDecider: HALT — %d critical block(s), %d violation(s).",
                len(critical_blocks),
                len(violations),
            )

        else:
            # Rule B: Any not-ok result from a required evaluator blocks execution.
            can_proceed = len(violations) == 0

            # Rule C: High-risk tiers require higher average confidence.
            confidence_threshold = 0.8 if risk_tier in ("ELEVATED", "CRITICAL") else 0.5
            if avg_confidence < confidence_threshold:
                can_proceed = False
                violations.append(
                    f"Confidence {avg_confidence:.2f} below threshold "
                    f"{confidence_threshold} for {risk_tier} tier."
                )

            all_blockers = violations
            decision = "PROCEED" if can_proceed else "HALT"

        # ── 3. Mandatory Decision Tracing ─────────────────────────────────────
        self.tracer.record(
            agent=self.component_id,
            decision_type="final_authorization",
            rationale=(
                f"Decision {decision} based on {len(evaluation_results)} evaluation(s) "
                f"at {risk_tier} tier. "
                f"Critical blocks: {len(critical_blocks)}. "
                f"Violations: {len(violations)}. "
                f"Avg confidence: {avg_confidence:.2f}."
            ),
            chosen_action=decision,
            context={
                "critical_blocks": critical_blocks,
                "violations": all_blockers,
                "warnings": warnings,
                "avg_confidence": avg_confidence,
                "risk_tier": risk_tier,
            },
            confidence=avg_confidence,
        )

        duration = time.time() - start_time

        return ComponentResult(
            component_id=self.component_id,
            ok=True,  # The Decider itself succeeded in producing a decision.
            data={
                "decision": decision,
                "can_proceed": can_proceed,
                "authorization_token": (
                    f"auth_{int(time.time())}" if can_proceed else None
                ),
                "blockers": all_blockers,
                "critical_blocks": critical_blocks,
                "warnings": warnings,
            },
            phase=self.phase,
            confidence=1.0,
            metadata={"verdict": decision, "risk_tier": risk_tier},
            duration_sec=duration,
        )
