# src/body/validators/logic_conservation_validator.py
"""
LogicConservationValidator — AUDIT phase component.

Constitutional gate: prevents the autonomous loop from accepting a generated
code proposal that deletes significant logic without explicit authorisation.

This is the constitutional implementation of the 'Anti-Lobotomy' gate defined
in CORE-PAPER-005 (First Octopus Field Test) and specified in the post-mortem
as Phase 3.2.

The gate is intentionally dumb. It does not understand semantics. It measures
mass: if the proposed output is less than THRESHOLD of the original size across
all files in the proposal, the gate fires. No LLM. No interpretation. Pure rule.

Constitutional alignment:
- Layer:     body — fact extraction and validation, no decisions
- Phase:     AUDIT — evaluates quality, produces binary verdict
- Authority: constitution — this gate cannot be bypassed by policy
- Boundary:  no Will imports, no DecisionTracer, no get_session

LAYER: body/validators — AUDIT phase evaluator. No side effects. No DB access.
No LLM. Pure deterministic measurement.
"""

from __future__ import annotations

import time

from body.evaluators.base_evaluator import BaseEvaluator
from shared.component_primitive import ComponentPhase, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)

# Constitutional threshold: proposals shrinking total code below this fraction
# of the original are treated as logic evaporation events.
# Declared here as a module constant — not a magic number buried in a method.
# To change this threshold, a constitutional proposal is required.
_CONSERVATION_THRESHOLD: float = 0.50

# Flag that a caller may include in kwargs to explicitly authorise large deletions.
# Example: a deliberate dead-code purge workflow sets deletions_authorized=True.
_AUTHORISATION_FLAG: str = "deletions_authorized"


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
class LogicConservationValidator(BaseEvaluator):
    """
    AUDIT phase validator.

    Measures the mass ratio between the proposed code map and the original
    source. Fires a CRITICAL violation when the ratio falls below the
    constitutional threshold and no explicit authorisation flag is present.

    Responsibilities (exactly one):
        Determine whether a proposed code change conserves sufficient logic mass.

    Not responsible for:
        - Deciding whether to accept or reject the proposal (that is GovernanceDecider)
        - Understanding what the code does (that is the LLM)
        - Choosing a recovery strategy (that is the Will layer)
    """

    @property
    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
    def component_id(self) -> str:
        return "logic_conservation_validator"

    @property
    # ID: c3d4e5f6-a7b8-9012-cdef-123456789012
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    # ID: d4e5f6a7-b8c9-0123-defa-234567890123
    async def evaluate(
        self,
        original_code: str,
        proposed_map: dict[str, str],
        deletions_authorized: bool = False,
        **kwargs: object,
    ) -> ComponentResult:
        """
        Evaluate whether the proposed code map conserves sufficient logic mass.

        Args:
            original_code:        The full source of the file before modification.
            proposed_map:         Dict mapping file paths to proposed code strings.
                                  A single-file refactor has one entry.
                                  A split refactor has multiple entries — the total
                                  mass of all outputs is compared against the original.
            deletions_authorized: If True, the mass check is skipped and the result
                                  is always ok=True. This flag must be set explicitly
                                  by the calling workflow — it is never inferred.

        Returns:
            ComponentResult with:
                ok=True   — mass is conserved, or deletions are authorised
                ok=False  — logic evaporation detected, gate fires
        """
        start = time.time()

        orig_len = len(original_code)

        # Guard: empty original is a degenerate case — let it through.
        # An empty file has nothing to conserve.
        if orig_len == 0:
            return ComponentResult(
                component_id=self.component_id,
                ok=True,
                data={
                    "verdict": "conserved",
                    "reason": "original_empty",
                    "original_length": 0,
                    "proposed_length": sum(len(c) for c in proposed_map.values()),
                    "ratio": 1.0,
                    "threshold": _CONSERVATION_THRESHOLD,
                },
                phase=self.phase,
                confidence=1.0,
                duration_sec=time.time() - start,
            )

        proposed_total = sum(len(code) for code in proposed_map.values())
        ratio = proposed_total / orig_len

        # Authorised bypass — caller explicitly declared large deletions are intended.
        if deletions_authorized:
            logger.info(
                "LogicConservationValidator: deletions_authorized=True — "
                "mass check bypassed (ratio=%.2f).",
                ratio,
            )
            return ComponentResult(
                component_id=self.component_id,
                ok=True,
                data={
                    "verdict": "authorized_deletion",
                    "original_length": orig_len,
                    "proposed_length": proposed_total,
                    "ratio": ratio,
                    "threshold": _CONSERVATION_THRESHOLD,
                    "deletions_authorized": True,
                },
                phase=self.phase,
                confidence=1.0,
                metadata={"violation_count": 0},
                duration_sec=time.time() - start,
            )

        # Main gate: fire if below threshold.
        if ratio < _CONSERVATION_THRESHOLD:
            logger.warning(
                "LogicConservationValidator: LOGIC EVAPORATION detected. "
                "Proposed code is %.1f%% of original (threshold: %.0f%%). "
                "Files in proposal: %s",
                ratio * 100,
                _CONSERVATION_THRESHOLD * 100,
                list(proposed_map.keys()),
            )
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={
                    "verdict": "logic_evaporation",
                    "violation": "logic.conservation.evaporation",
                    "original_length": orig_len,
                    "proposed_length": proposed_total,
                    "ratio": ratio,
                    "threshold": _CONSERVATION_THRESHOLD,
                    "files_in_proposal": list(proposed_map.keys()),
                    "message": (
                        f"Proposed code is {ratio * 100:.1f}% of original size "
                        f"(minimum {_CONSERVATION_THRESHOLD * 100:.0f}%). "
                        "Set deletions_authorized=True to permit large removals."
                    ),
                },
                phase=self.phase,
                confidence=1.0,
                metadata={"violation_count": 1},
                duration_sec=time.time() - start,
            )

        logger.debug(
            "LogicConservationValidator: mass conserved (ratio=%.2f, threshold=%.2f).",
            ratio,
            _CONSERVATION_THRESHOLD,
        )
        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            data={
                "verdict": "conserved",
                "original_length": orig_len,
                "proposed_length": proposed_total,
                "ratio": ratio,
                "threshold": _CONSERVATION_THRESHOLD,
            },
            phase=self.phase,
            confidence=1.0,
            metadata={"violation_count": 0},
            duration_sec=time.time() - start,
        )
