# src/mind/governance/validator_service.py

"""
Constitutional Validator Service - Backward Compatibility Wrapper

CONSTITUTIONAL FIX: This file now acts as a compatibility layer that delegates
to the new constitutionally-compliant architecture:

- Mind layer (governance_query.py) - Pure query interface to .intent/
- Body layer (risk_classification_service.py) - Execution logic

This wrapper maintains backward compatibility while the codebase migrates
to the new structure. Once all imports are updated, this file can be deprecated.

Migration Status:
- OLD: Mind layer executed risk classification (VIOLATION)
- NEW: Mind queries, Body executes, this wraps for compatibility
- NEXT: Update all imports to use Body service directly
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# Re-export types for backward compatibility
# ID: 9a021d9a-929d-4047-afaa-dc9787d92d48
class RiskTier(Enum):
    """Risk classification for operations."""

    ROUTINE = 1
    STANDARD = 3
    ELEVATED = 7
    CRITICAL = 10


# ID: 50d2f68f-9762-421f-bfeb-14cc31a33cb7
class ApprovalType(Enum):
    """Approval mechanism required."""

    AUTONOMOUS = "autonomous"
    VALIDATION_ONLY = "validation_only"
    HUMAN_CONFIRMATION = "human_confirmation"
    HUMAN_REVIEW = "human_review"


@dataclass
# ID: 8ef911d6-c71d-4af7-977c-c6e2e44a522e
class GovernanceDecision:
    """Result of governance validation."""

    allowed: bool
    risk_tier: RiskTier
    approval_type: ApprovalType
    rationale: str
    violations: list[str]


# ID: 20d58174-52af-405a-8ee7-043f5b43f914
class ConstitutionalValidator:
    """
    BACKWARD COMPATIBILITY WRAPPER

    This class maintains the old API while delegating to the new
    constitutionally-compliant architecture.

    Constitutional Architecture:
    - Mind layer: governance_query.py (loads .intent/ documents)
    - Body layer: risk_classification_service.py (executes classification)
    - This wrapper: Maintains old API during migration

    Deprecated: Use RiskClassificationService directly from Body layer
    """

    def __init__(self, constitution_path: Path | None = None):
        """
        Initialize validator with constitutional documents.

        Args:
            constitution_path: Path to .intent/ directory (optional)
        """
        if constitution_path is None:
            constitution_path = Path(".intent")

        self.constitution_path = constitution_path
        self._constitution: dict[str, Any] = {}

        # CONSTITUTIONAL FIX: Delegate to Mind layer for governance query
        from mind.governance.governance_query import GovernanceQuery

        self._mind_query = GovernanceQuery(constitution_path)

        # Load constitution through Mind layer
        self._load_constitution()

        # CONSTITUTIONAL FIX: Delegate to Body layer for execution
        from body.governance.risk_classification_service import (
            RiskClassificationService,
        )

        self._body_service = RiskClassificationService(self._constitution)

    def _load_constitution(self):
        """
        Load constitutional documents through Mind layer.

        CONSTITUTIONAL FIX: Uses Mind layer's governance_query interface
        instead of loading directly (which was a layer violation).
        """
        self._constitution = self._mind_query.load_constitution()
        logger.info("Loaded constitution via Mind layer governance query")

    # Delegate all execution methods to Body layer service

    @lru_cache(maxsize=1024)
    # ID: fef293b7-e474-437b-84fc-eeeabf33f49b
    def is_action_autonomous(self, action: str) -> bool:
        """Check if action is approved for autonomous execution."""
        return self._body_service.is_action_autonomous(action)

    @lru_cache(maxsize=1024)
    # ID: 3d5fd3e2-c279-4744-9fe3-21d6c1cba9fe
    def is_action_prohibited(self, action: str) -> bool:
        """Check if action is explicitly prohibited."""
        return self._body_service.is_action_prohibited(action)

    # ID: 05cadd67-c934-44a2-95b1-0e17d89762c2
    def is_boundary_violation(self, action: str, context: dict[str, Any]) -> list[str]:
        """Check if action violates immutable boundaries."""
        return self._body_service.is_boundary_violation(action, context)

    @lru_cache(maxsize=512)
    # ID: 53428e94-93d0-4ad3-8c3b-1e493754eeac
    def classify_risk(self, filepath: str, action: str) -> RiskTier:
        """
        Classify operation risk.

        CONSTITUTIONAL FIX: Delegates to Body layer service
        """
        body_risk = self._body_service.classify_risk(filepath, action)

        # Convert Body layer RiskTier to this module's RiskTier
        # (they have different numeric values for backward compatibility)
        tier_mapping = {
            0: RiskTier.ROUTINE,  # Body: 0 -> Legacy: 1
            1: RiskTier.STANDARD,  # Body: 1 -> Legacy: 3
            2: RiskTier.ELEVATED,  # Body: 2 -> Legacy: 7
            3: RiskTier.CRITICAL,  # Body: 3 -> Legacy: 10
        }
        return tier_mapping[body_risk.value]

    # ID: bee5b7ad-75e3-4293-a1af-1633a004e126
    def can_execute_autonomously(
        self, filepath: str, action: str, context: dict[str, Any] | None = None
    ) -> GovernanceDecision:
        """
        Primary governance decision function.

        CONSTITUTIONAL FIX: Delegates to Body layer service
        """
        body_decision = self._body_service.can_execute_autonomously(
            filepath, action, context
        )

        # Convert Body layer decision to this module's GovernanceDecision
        tier_mapping = {
            0: RiskTier.ROUTINE,
            1: RiskTier.STANDARD,
            2: RiskTier.ELEVATED,
            3: RiskTier.CRITICAL,
        }

        approval_mapping = {
            "autonomous": ApprovalType.AUTONOMOUS,
            "validation_only": ApprovalType.VALIDATION_ONLY,
            "human_confirmation": ApprovalType.HUMAN_CONFIRMATION,
            "human_review": ApprovalType.HUMAN_REVIEW,
        }

        return GovernanceDecision(
            allowed=body_decision.allowed,
            risk_tier=tier_mapping[body_decision.risk_tier.value],
            approval_type=approval_mapping[body_decision.approval_type.value],
            rationale=body_decision.rationale,
            violations=body_decision.violations,
        )


# Singleton instance for backward compatibility
_VALIDATOR_INSTANCE: ConstitutionalValidator | None = None


# ID: get-validator
# ID: fab39c7e-4d1b-4a8f-9e2c-1234567890ab
def get_validator(constitution_path: Path | None = None) -> ConstitutionalValidator:
    """
    Get singleton validator instance.

    BACKWARD COMPATIBILITY: This function maintains the old API.

    MIGRATION PATH:
    Instead of:
        from mind.governance.validator_service import get_validator
        validator = get_validator()
        decision = validator.can_execute_autonomously(filepath, action)

    Use directly:
        from mind.governance.governance_query import get_governance_query
        from body.governance.risk_classification_service import RiskClassificationService

        query = get_governance_query()
        constitution = query.load_constitution()
        service = RiskClassificationService(constitution)
        decision = service.can_execute_autonomously(filepath, action)

    Args:
        constitution_path: Optional path to .intent/ directory

    Returns:
        ConstitutionalValidator singleton instance
    """
    global _VALIDATOR_INSTANCE

    if _VALIDATOR_INSTANCE is None:
        _VALIDATOR_INSTANCE = ConstitutionalValidator(constitution_path)
        logger.info("Initialized ConstitutionalValidator (compatibility wrapper)")

    return _VALIDATOR_INSTANCE


# Convenience functions for backward compatibility
# These delegate to the singleton validator instance


# ID: is-action-autonomous-func
# ID: e0f4b7c3-925b-452f-b59f-5167f9280411
def is_action_autonomous(action: str) -> bool:
    """Check if action is autonomous (backward compatibility)."""
    return get_validator().is_action_autonomous(action)


# ID: classify-risk-func
# ID: af479369-925b-452f-b59f-5167f9280411
def classify_risk(filepath: str, action: str) -> RiskTier:
    """Classify operation risk (backward compatibility)."""
    return get_validator().classify_risk(filepath, action)


# ID: can-execute-autonomously-func
# ID: 9f1f43b2-fb0c-4728-bec8-32a245d6f51b
def can_execute_autonomously(
    filepath: str, action: str, context: dict[str, Any] | None = None
) -> GovernanceDecision:
    """Primary governance check (backward compatibility)."""
    return get_validator().can_execute_autonomously(filepath, action, context)


# Test harness for backward compatibility
if __name__ == "__main__":
    validator = get_validator()
    logger.info("\n" + "=" * 80)
    logger.info("CONSTITUTIONAL VALIDATOR TEST (Compatibility Wrapper)")
    logger.info("=" * 80)

    test_cases = [
        ("src/body/commands/fix.py", "fix_docstring"),
        ("src/mind/governance/validator_service.py", "format_code"),
        (".intent/charter/constitution/authority.json", "edit_file"),
        ("src/body/services/database.py", "schema_migration"),
        ("docs/README.md", "update_docs"),
        ("tests/test_core.py", "generate_tests"),
        ("src/body/core/database.py", "refactoring"),
    ]

    for filepath, action in test_cases:
        decision = can_execute_autonomously(filepath, action, {"filepath": filepath})
        logger.info("\n📋 Action: %s", action)
        logger.info("   Path: %s", filepath)
        logger.info("   Risk: %s", decision.risk_tier.name)
        logger.info("   Allowed: %s", decision.allowed)
        logger.info("   Approval: %s", decision.approval_type.value)
        logger.info("   Rationale: %s", decision.rationale)
        if decision.violations:
            logger.info("   Violations: %s", decision.violations)

    logger.info("\n" + "=" * 80)
    logger.info("NOTE: This is a compatibility wrapper.")
    logger.info("Consider migrating to direct Body layer usage.")
    logger.info("=" * 80)
