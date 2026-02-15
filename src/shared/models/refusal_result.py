# src/shared/models/refusal_result.py
# ID: 563f5740-d13f-4c76-be9c-e615eb80f3af

"""
First-class refusal outcome type.

Constitutional Principle:
"Refusal as a first-class outcome" - refusals are not exceptions or errors,
they are legitimate decision outcomes that must be traced and reported.

This module provides RefusalResult as a specialized ComponentResult that
represents an explicit, constitutional refusal to proceed with an operation.

Authority: Constitution (refusal discipline)
Phase: Runtime (any phase can refuse)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.component_primitive import ComponentPhase, ComponentResult


@dataclass
# ID: cd3e4f5a-6b7c-8d9e-0f1a-2b3c4d5e6f7a
class RefusalResult(ComponentResult):
    """
    First-class refusal outcome.

    RefusalResult is a ComponentResult where ok=False represents an explicit,
    constitutional refusal rather than a technical failure.

    Key Difference from Error:
    - Error: Something went wrong (unexpected, should be fixed)
    - Refusal: Explicitly chose not to proceed (expected, constitutionally valid)

    Constitutional Properties:
    - reason: Why refusal occurred (citing policy/rule)
    - suggested_action: What user should do instead
    - refusal_type: Category of refusal (boundary, confidence, contradiction, etc.)

    Attributes:
        reason: Constitutional reason for refusal (with policy citation)
        suggested_action: What user can do to address the refusal
        refusal_type: Category of refusal for tracking/analysis
        original_request: The request that was refused (for audit trail)
    """

    reason: str = ""
    """Why refusal occurred (must cite policy/rule)"""

    suggested_action: str = ""
    """What user should do instead"""

    refusal_type: str = "unspecified"
    """Category: boundary, confidence, contradiction, assumption, capability"""

    original_request: str = ""
    """The request that was refused (for audit trail)"""

    def __post_init__(self) -> None:
        """Enforce refusal result invariants."""
        # RefusalResult must always have ok=False
        if self.ok:
            raise ValueError(
                "RefusalResult must have ok=False. "
                "Use ComponentResult(ok=True) for successful outcomes."
            )

        # RefusalResult must have a reason
        if not self.reason:
            raise ValueError(
                "RefusalResult must have a reason. "
                "Refusals without explanation violate constitutional transparency."
            )

        # Refusal type must be valid
        valid_types = {
            "boundary",  # Hard boundary violation (e.g., .intent/ write attempt)
            "confidence",  # Low confidence interpretation
            "contradiction",  # Conflicting requirements
            "assumption",  # Required assumption user didn't confirm
            "capability",  # Beyond system capabilities
            "extraction",  # Cannot extract valid output from LLM
            "quality",  # Output quality below constitutional threshold
            "unspecified",  # Default when type not categorized
        }

        if self.refusal_type not in valid_types:
            raise ValueError(
                f"Invalid refusal_type: {self.refusal_type}. "
                f"Must be one of: {', '.join(sorted(valid_types))}"
            )

    @classmethod
    # ID: c92d7acc-06ae-4c41-8a3b-f4a3d94d3802
    def boundary_violation(
        cls,
        component_id: str,
        phase: ComponentPhase,
        reason: str,
        boundary: str,
        original_request: str = "",
    ) -> RefusalResult:
        """
        Create refusal for hard boundary violation.

        Args:
            component_id: Component that refused
            phase: Phase where refusal occurred
            reason: Why boundary was violated (with policy citation)
            boundary: Which boundary (.intent/, lane, etc.)
            original_request: What was attempted

        Returns:
            RefusalResult configured for boundary violation
        """
        return cls(
            component_id=component_id,
            ok=False,
            data={"boundary": boundary},
            phase=phase,
            confidence=1.0,  # Boundary violations are certain
            reason=reason,
            suggested_action=f"Request cannot cross {boundary} boundary. "
            "Modify request to work within constitutional boundaries.",
            refusal_type="boundary",
            original_request=original_request,
        )

    @classmethod
    # ID: a08d72d0-4065-48c7-9f8b-290d5de940c0
    def low_confidence(
        cls,
        component_id: str,
        phase: ComponentPhase,
        confidence: float,
        reason: str,
        original_request: str = "",
        alternatives: list[str] | None = None,
    ) -> RefusalResult:
        """
        Create refusal for low confidence interpretation.

        Args:
            component_id: Component that refused
            phase: Phase where refusal occurred
            confidence: Actual confidence score (should be < threshold)
            reason: Why confidence is too low
            original_request: What was attempted
            alternatives: Possible clarifications user could provide

        Returns:
            RefusalResult configured for low confidence
        """
        suggested = "Please clarify your request with more specific details."
        if alternatives:
            suggested += f" Consider: {', '.join(alternatives)}"

        return cls(
            component_id=component_id,
            ok=False,
            data={"confidence": confidence, "alternatives": alternatives or []},
            phase=phase,
            confidence=confidence,
            reason=reason,
            suggested_action=suggested,
            refusal_type="confidence",
            original_request=original_request,
        )

    @classmethod
    # ID: f5de8dde-34b6-411b-8696-21fa958aafda
    def extraction_failed(
        cls,
        component_id: str,
        phase: ComponentPhase,
        reason: str,
        llm_response_preview: str,
        original_request: str = "",
    ) -> RefusalResult:
        """
        Create refusal when LLM output cannot be extracted.

        Constitutional Principle:
        When primary extraction fails, REFUSE rather than silently repair.

        Args:
            component_id: Component that refused
            phase: Phase where refusal occurred
            reason: Why extraction failed (with details)
            llm_response_preview: Preview of malformed response (for debugging)
            original_request: Original generation request

        Returns:
            RefusalResult configured for extraction failure
        """
        return cls(
            component_id=component_id,
            ok=False,
            data={
                "llm_response_preview": llm_response_preview[:500],
                "extraction_method": "primary",
            },
            phase=phase,
            confidence=0.0,  # Cannot extract = zero confidence
            reason=reason,
            suggested_action="LLM response was malformed. "
            "Retry with more explicit prompt formatting instructions, "
            "or adjust LLM temperature/parameters.",
            refusal_type="extraction",
            original_request=original_request,
        )

    @classmethod
    # ID: 10b72e4d-080b-45c2-ba10-cf5f675962d5
    def quality_threshold(
        cls,
        component_id: str,
        phase: ComponentPhase,
        reason: str,
        quality_metrics: dict[str, Any],
        original_request: str = "",
    ) -> RefusalResult:
        """
        Create refusal when output quality below constitutional threshold.

        Args:
            component_id: Component that refused
            phase: Phase where refusal occurred
            reason: Why quality is insufficient (with metrics)
            quality_metrics: Measured quality values
            original_request: What was attempted

        Returns:
            RefusalResult configured for quality threshold
        """
        return cls(
            component_id=component_id,
            ok=False,
            data={"quality_metrics": quality_metrics},
            phase=phase,
            confidence=0.3,  # Low quality = low confidence
            reason=reason,
            suggested_action="Generated output does not meet constitutional quality standards. "
            "Review requirements and retry with enhanced context.",
            refusal_type="quality",
            original_request=original_request,
        )

    # ID: 62ae8943-9098-40c1-932a-d070aeed647a
    def to_user_message(self) -> str:
        """
        Format refusal as user-facing message.

        Returns:
            Human-readable refusal explanation
        """
        lines = [
            f"Cannot proceed: {self.reason}",
            "",
        ]

        if self.suggested_action:
            lines.append(f"Suggestion: {self.suggested_action}")

        if self.refusal_type != "unspecified":
            lines.append(f"Refusal type: {self.refusal_type}")

        if self.original_request:
            lines.append("")
            lines.append(f"Original request: {self.original_request}")

        return "\n".join(lines)

    # ID: 239d9dc0-f7bc-482f-937b-ee95ecaa29f7
    def to_trace_entry(self) -> dict[str, Any]:
        """
        Format refusal for decision trace.

        Returns:
            Dict suitable for DecisionTracer.record()
        """
        return {
            "decision_type": "refusal",
            "refusal_type": self.refusal_type,
            "reason": self.reason,
            "suggested_action": self.suggested_action,
            "original_request": self.original_request,
            "component_id": self.component_id,
            "phase": self.phase.value if self.phase else "unknown",
            "confidence": self.confidence,
        }
