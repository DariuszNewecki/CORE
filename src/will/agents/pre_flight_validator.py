# src/will/agents/pre_flight_validator.py
"""
Pre-Flight Constitutional Validator - Integration Layer.

Wires AuthorityPackageBuilder into the code generation workflow.
Called by CoderAgent BEFORE any LLM code generation occurs.

CONSTITUTIONAL PRINCIPLE:
"Check legality before generating code, not after."

This module provides the integration point between:
- Existing CoderAgent (code generation)
- New AuthorityPackageBuilder (constitutional validation)

Flow:
    CoderAgent.generate_code()
        ↓
    PreFlightValidator.validate_request()  ← NEW GATE
        ↓
    [Constitutional validation happens]
        ↓
    Returns: AuthorityPackage or Refusal
        ↓
    If valid: Proceed to LLM generation
    If invalid: Return refusal to user

Authority: Policy (constitutional enforcement)
Phase: Pre-flight (before code generation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.authority_package_builder import AuthorityPackageBuilder
    from shared.infrastructure.intent.intent_repository import IntentRepository
    from will.tools.policy_vectorizer import PolicyVectorizer

logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
@dataclass
# ID: ef51123a-09c0-4555-883b-dd86db868ba7
class ValidationResult:
    """
    Result of pre-flight constitutional validation.

    Either authorizes generation (with authority package)
    or refuses it (with explanation).
    """

    authorized: bool
    """Whether code generation is authorized"""

    authority_package: Any | None = None
    """Complete authority package if authorized"""

    refusal_reason: str | None = None
    """Why generation was refused (if not authorized)"""

    user_message: str | None = None
    """Message to present to user (assumptions, contradictions, etc.)"""


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class PreFlightValidator:
    """
    Integration layer for constitutional pre-flight validation.

    This class provides a simple interface for CoderAgent to validate
    requests before code generation without needing to understand the
    full complexity of the constitutional validation pipeline.

    Usage in CoderAgent:
        validator = PreFlightValidator(...)

        result = await validator.validate_request(user_request)

        if not result.authorized:
            return Refusal(reason=result.refusal_reason)

        # Proceed with generation, including authority in context
        code = await self.generate_with_authority(
            user_request,
            authority=result.authority_package
        )
    """

    def __init__(
        self,
        authority_builder: AuthorityPackageBuilder,
        enable_pre_flight: bool = True,
    ):
        """
        Initialize pre-flight validator.

        Args:
            authority_builder: AuthorityPackageBuilder for validation
            enable_pre_flight: Whether to actually validate (allows gradual rollout)
        """
        self.authority_builder = authority_builder
        self.enable_pre_flight = enable_pre_flight

        if not enable_pre_flight:
            logger.warning(
                "⚠️  Pre-flight validation DISABLED. "
                "Code will be generated without constitutional checks."
            )

    # ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
    async def validate_request(
        self, user_request: str, interactive: bool = True
    ) -> ValidationResult:
        """
        Validate user request before code generation.

        Args:
            user_request: User's natural language request
            interactive: Whether to prompt user for confirmations

        Returns:
            ValidationResult indicating authorization or refusal

        Process:
        1. Build authority package (runs all 5 gates)
        2. Check if valid for generation
        3. If has assumptions and interactive, prompt user
        4. Return authorization or refusal
        """
        # Bypass if disabled (gradual rollout support)
        if not self.enable_pre_flight:
            logger.debug("Pre-flight validation bypassed (disabled)")
            return ValidationResult(authorized=True)

        logger.info("🔐 Running pre-flight constitutional validation...")

        try:
            # Build authority package (runs all gates)
            package = await self.authority_builder.build_from_request(user_request)

            # Check for immediate failures
            if package.contradictions:
                return self._handle_contradictions(package)

            if package.refusal_reason:
                return self._handle_refusal(package)

            # Check if assumptions need user confirmation
            if package.assumptions and interactive:
                return await self._handle_assumptions(package)

            # All gates passed
            logger.info("✅ Pre-flight validation passed")
            return ValidationResult(
                authorized=True,
                authority_package=package,
            )

        except Exception as e:
            logger.error(
                "Pre-flight validation failed with exception: %s", e, exc_info=True
            )
            return ValidationResult(
                authorized=False,
                refusal_reason=f"Validation error: {e}",
            )

    # ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
    def _handle_contradictions(self, package) -> ValidationResult:
        """
        Handle contradictory requirements.

        Args:
            package: Authority package with contradictions

        Returns:
            ValidationResult with refusal
        """
        logger.warning("❌ Constitutional contradictions detected")

        # Format user message
        lines = [
            "Cannot proceed. Your request contains contradictory requirements:",
            "",
        ]

        for contradiction in package.contradictions:
            lines.append(f"  Conflict: {contradiction.rule1_id}")
            lines.append(f"       vs : {contradiction.rule2_id}")
            lines.append(f"  Pattern: {contradiction.pattern}")
            lines.append("")

        lines.append("Please resolve conflicts by:")
        lines.append("  1. Modifying your request to avoid contradictions, or")
        lines.append("  2. Explicitly stating which policy takes precedence")

        user_message = "\n".join(lines)

        return ValidationResult(
            authorized=False,
            refusal_reason="Constitutional contradictions detected",
            user_message=user_message,
        )

    # ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
    def _handle_refusal(self, package) -> ValidationResult:
        """
        Handle explicit refusal.

        Args:
            package: Authority package with refusal reason

        Returns:
            ValidationResult with refusal
        """
        logger.warning("❌ Generation refused: %s", package.refusal_reason)

        return ValidationResult(
            authorized=False,
            refusal_reason=package.refusal_reason,
            user_message=f"Cannot proceed: {package.refusal_reason}",
        )

    # ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
    async def _handle_assumptions(self, package) -> ValidationResult:
        """
        Handle assumptions requiring user confirmation.

        Args:
            package: Authority package with assumptions

        Returns:
            ValidationResult based on user confirmation
        """
        logger.info("📋 Presenting %d assumptions to user...", len(package.assumptions))

        # Format assumptions for user
        lines = [
            "I will make the following assumptions based on constitutional policies:",
            "",
        ]

        for assumption in package.assumptions:
            lines.append(f"  • {assumption.aspect}: {assumption.suggested_value}")
            lines.append(f"    Citation: {assumption.cited_policy}")
            lines.append(f"    Rationale: {assumption.rationale}")
            lines.append("")

        user_message = "\n".join(lines)

        # In a real implementation, this would prompt the user
        # For now, we'll auto-approve (can be wired to CLI/UI)
        logger.info("Auto-approving assumptions (interactive mode not implemented)")

        # Confirm authority package
        package = await self.authority_builder.confirm_authority_package(
            package, user_approval=True
        )

        return ValidationResult(
            authorized=True,
            authority_package=package,
            user_message=user_message,
        )

    # ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
    def format_authority_for_prompt(self, authority_package) -> str:
        """
        Format authority package for inclusion in LLM prompt.

        Args:
            authority_package: Validated authority package

        Returns:
            Formatted string to include in code generation prompt

        This ensures the LLM respects constitutional constraints.
        """
        if not authority_package:
            return ""

        lines = [
            "CONSTITUTIONAL AUTHORITY:",
            "",
            "You must generate code respecting these constraints:",
            "",
        ]

        # Include constitutional constraints
        if authority_package.constitutional_constraints:
            lines.append("Hard Constraints:")
            for constraint in authority_package.constitutional_constraints:
                lines.append(f"  - {constraint}")
            lines.append("")

        # Include confirmed assumptions
        if authority_package.assumptions:
            lines.append("Confirmed Assumptions:")
            for assumption in authority_package.assumptions:
                lines.append(f"  - {assumption.aspect}: {assumption.suggested_value}")
                lines.append(f"    (per {assumption.cited_policy})")
            lines.append("")

        # Include matched policies
        if authority_package.matched_policies:
            lines.append("Governing Policies:")
            for policy in authority_package.matched_policies[:3]:  # Top 3
                lines.append(f"  - {policy.rule_id}: {policy.statement[:60]}...")
            lines.append("")

        return "\n".join(lines)


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
async def create_pre_flight_validator(
    intent_repository: IntentRepository,
    policy_vectorizer: PolicyVectorizer,
    cognitive_service,
    enable_pre_flight: bool = True,
) -> PreFlightValidator:
    """
    Factory function to create PreFlightValidator with all dependencies.

    Args:
        intent_repository: IntentRepository for loading policies
        policy_vectorizer: PolicyVectorizer for semantic search
        cognitive_service: CognitiveService for LLM operations
        enable_pre_flight: Whether to enable validation (gradual rollout)

    Returns:
        Configured PreFlightValidator

    This handles wiring all the components together:
    - RequestInterpreter
    - AssumptionExtractor
    - RuleConflictDetector
    - AuthorityPackageBuilder
    """
    from body.governance.rule_conflict_detector import RuleConflictDetector
    from mind.governance.assumption_extractor import AssumptionExtractor
    from mind.governance.authority_package_builder import AuthorityPackageBuilder
    from will.interpreters.request_interpreter import NaturalLanguageInterpreter

    # Create components
    interpreter = NaturalLanguageInterpreter()

    assumption_extractor = AssumptionExtractor(
        intent_repository=intent_repository,
        policy_vectorizer=policy_vectorizer,
        cognitive_service=cognitive_service,
    )

    conflict_detector = RuleConflictDetector()

    authority_builder = AuthorityPackageBuilder(
        request_interpreter=interpreter,
        intent_repository=intent_repository,
        policy_vectorizer=policy_vectorizer,
        assumption_extractor=assumption_extractor,
        rule_conflict_detector=conflict_detector,
    )

    # Create validator
    validator = PreFlightValidator(
        authority_builder=authority_builder,
        enable_pre_flight=enable_pre_flight,
    )

    logger.info("✅ PreFlightValidator created (enabled=%s)", enable_pre_flight)

    return validator
