# src/will/deciders/governance_decider.py
# ID: 8ef911d6-c71d-4af7-977c-c6e2e44a522e

"""
Governance Decider - DECIDE Phase Component.
The final gatekeeper that authorizes or blocks state-changing execution.
"""

from __future__ import annotations

import time
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: 79a654be-b451-4932-93fe-d90b4a8f7a77
class GovernanceDecider(Component):
    """
    Evaluates cumulative evidence to authorize execution.

    Responsibilities:
    - Aggregate results from multiple Evaluators.
    - Check for 'Blocking' violations.
    - Evaluate if 'Confidence' meets the threshold for the Risk Tier.
    - Produce a formal 'Authorization Token' or 'Halt' signal.
    """

    def __init__(self):
        self.tracer = DecisionTracer()

    @property
    # ID: 49f7bb27-237b-4e40-aa91-03b5eea8a36f
    def phase(self) -> ComponentPhase:
        return ComponentPhase.RUNTIME  # DECIDE happens at the end of Runtime

    # ID: c2aeb827-6b0d-4036-8fca-a01fc2244524
    async def execute(
        self,
        evaluation_results: list[ComponentResult],
        risk_tier: str = "STANDARD",
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Make a final Go/No-Go decision.
        """
        start_time = time.time()

        violations = []
        warnings = []
        total_confidence = 0.0

        # 1. Aggregate Evidence
        for res in evaluation_results:
            if not res.ok:
                violations.append(
                    f"{res.component_id}: {res.data.get('error', 'Unknown failure')}"
                )

            # Collect warnings from metadata
            if (
                "violation_count" in res.metadata
                and res.metadata["violation_count"] > 0
            ):
                warnings.append(
                    f"{res.component_id} found {res.metadata['violation_count']} issues."
                )

            total_confidence += res.confidence

        avg_confidence = (
            total_confidence / len(evaluation_results) if evaluation_results else 1.0
        )

        # 2. Decision Logic (The Law)
        # Rule: Any 'not ok' result from a required Evaluator blocks execution.
        can_proceed = len(violations) == 0

        # Rule: High-risk tiers require higher confidence
        confidence_threshold = 0.8 if risk_tier in ["ELEVATED", "CRITICAL"] else 0.5
        if avg_confidence < confidence_threshold:
            can_proceed = False
            violations.append(
                f"Confidence {avg_confidence:.2f} is below threshold {confidence_threshold} for {risk_tier} tier."
            )

        decision = "PROCEED" if can_proceed else "HALT"

        # 3. Mandatory Decision Tracing
        self.tracer.record(
            agent=self.component_id,
            decision_type="final_authorization",
            rationale=f"Decision {decision} based on {len(evaluation_results)} evaluations at {risk_tier} tier.",
            chosen_action=decision,
            context={
                "violations": violations,
                "warnings": warnings,
                "avg_confidence": avg_confidence,
                "risk_tier": risk_tier,
            },
            confidence=avg_confidence,
        )

        duration = time.time() - start_time

        return ComponentResult(
            component_id=self.component_id,
            ok=True,  # The Decider itself succeeded in making a decision
            data={
                "decision": decision,
                "can_proceed": can_proceed,
                "authorization_token": (
                    f"auth_{int(time.time())}" if can_proceed else None
                ),
                "blockers": violations,
            },
            phase=self.phase,
            confidence=1.0,
            metadata={"verdict": decision, "risk_tier": risk_tier},
            duration_sec=duration,
        )
