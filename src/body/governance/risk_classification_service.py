# src/body/governance/risk_classification_service.py
"""
Risk Classification Service - Body Layer

CONSTITUTIONAL FIX: Moved from src/mind/governance/base/risk_classifier.py

This service performs risk classification execution logic, which belongs in Body layer.
Mind layer should only provide query interfaces to .intent/ documents.

Constitutional Compliance:
- Body layer component (execution, not governance definition)
- Reads constitutional rules from Mind layer
- Implements decision logic for risk assessment
- Used by Will layer for governance decisions

Migration Notes:
- Previously: src/mind/governance/base/risk_classifier.py (CONSTITUTIONAL VIOLATION)
- Now: src/body/governance/risk_classification_service.py (COMPLIANT)
- Rationale: Risk classification is execution logic, not law definition
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: enum-risk-tier
# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
class RiskTier(Enum):
    """Risk classification tiers for autonomous operations."""

    ROUTINE = 0  # Safe for full autonomous execution
    STANDARD = 1  # Requires validation but can proceed
    ELEVATED = 2  # Requires human confirmation
    CRITICAL = 3  # Requires comprehensive human review


# ID: enum-approval-type
# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class ApprovalType(Enum):
    """Types of approval required for operations."""

    AUTONOMOUS = "autonomous"  # AI can execute without human intervention
    VALIDATION_ONLY = "validation_only"  # AI can execute, human validates after
    HUMAN_CONFIRMATION = "human_confirmation"  # Human must approve before execution
    HUMAN_REVIEW = "human_review"  # Comprehensive human review required


@dataclass
# ID: dataclass-governance-decision
# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class GovernanceDecision:
    """Result of governance check for autonomous operations."""

    allowed: bool
    risk_tier: RiskTier
    approval_type: ApprovalType
    rationale: str
    violations: list[str]


# ID: class-risk-classification-service
# ID: a0b1c2d3-e4f5-6a7b-8c9d-0e1f2a3b4c5d
class RiskClassificationService:
    """
    Body layer service for risk classification and governance decisions.

    CONSTITUTIONAL ROLE:
    - Executes risk assessment logic (Body responsibility)
    - Reads governance rules from Mind layer
    - Provides decision support to Will layer
    - Does NOT define law (that's Mind's role)

    This service implements the operational logic that interprets
    constitutional rules and applies them to specific file/action combinations.
    """

    def __init__(self, constitution: dict[str, Any]):
        """
        Initialize risk classification service with constitutional rules.

        Args:
            constitution: Constitutional rules loaded from Mind layer
        """
        self._constitution = constitution
        self._critical_paths: set[str] = set()
        self._autonomous_actions: set[str] = set()
        self._prohibited_actions: set[str] = set()
        self._risk_by_path: dict[str, RiskTier] = {}
        self._risk_by_action: dict[str, RiskTier] = {}

        # Index constitutional rules for fast lookup
        self._index_constitutional_rules()

    def _index_constitutional_rules(self) -> None:
        """
        Index constitutional rules from Mind layer for efficient lookup.

        This method parses the constitution and builds internal indexes
        for path patterns, actions, and risk tiers.
        """
        # Index authority rules
        if "authority" in self._constitution:
            auth = self._constitution["authority"]
            for principle_id, principle in auth.get("principles", {}).items():
                enforcement = principle.get("enforcement", {})
                params = enforcement.get("parameters", {})

                # Index autonomous actions
                if "actions_allowed" in params:
                    actions = params["actions_allowed"]
                    if isinstance(actions, list):
                        self._autonomous_actions.update(actions)
                    elif isinstance(actions, str):
                        self._autonomous_actions.update(actions.split())

                # Index prohibited actions
                if "actions_prohibited" in params:
                    actions = params["actions_prohibited"]
                    if isinstance(actions, list):
                        self._prohibited_actions.update(actions)
                    elif isinstance(actions, str):
                        self._prohibited_actions.update(actions.split())

                # Index critical paths
                if "patterns" in params:
                    patterns = params["patterns"]
                    if isinstance(patterns, list):
                        for pattern in patterns:
                            if (
                                "critical" in principle_id
                                or "constitutional" in principle_id
                            ):
                                self._critical_paths.add(pattern)
                    elif isinstance(patterns, str):
                        for pattern in patterns.split():
                            if (
                                "critical" in principle_id
                                or "constitutional" in principle_id
                            ):
                                self._critical_paths.add(pattern)

        # Index risk tier mappings
        if "risk" in self._constitution:
            risk = self._constitution["risk"]
            for principle_id, principle in risk.get("principles", {}).items():
                enforcement = principle.get("enforcement", {})
                params = enforcement.get("parameters", {})

                # Index path-based risk tiers
                for tier_name, tier_value in [
                    ("critical", RiskTier.CRITICAL),
                    ("elevated", RiskTier.ELEVATED),
                    ("standard", RiskTier.STANDARD),
                    ("routine", RiskTier.ROUTINE),
                ]:
                    if tier_name in params:
                        paths = params[tier_name]
                        if isinstance(paths, str):
                            for path in paths.split():
                                self._risk_by_path[path] = tier_value
                        elif isinstance(paths, list):
                            for path in paths:
                                self._risk_by_path[path] = tier_value

                # Index action-based risk tiers
                if "actions" in params:
                    actions_by_tier = params["actions"]
                    for tier_name, actions in actions_by_tier.items():
                        tier_value = RiskTier[tier_name.upper()]
                        if isinstance(actions, list):
                            for action in actions:
                                self._risk_by_action[action] = tier_value
                        elif isinstance(actions, str):
                            for action in actions.split():
                                self._risk_by_action[action] = tier_value

    @lru_cache(maxsize=1024)
    # ID: is-action-autonomous
    # ID: b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
    def is_action_autonomous(self, action: str) -> bool:
        """
        Check if action is approved for autonomous execution.

        Args:
            action: Action type (e.g., "format_code", "fix_docstring")

        Returns:
            True if action is in autonomous-allowed list
        """
        return action in self._autonomous_actions

    @lru_cache(maxsize=1024)
    # ID: is-action-prohibited
    # ID: c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f
    def is_action_prohibited(self, action: str) -> bool:
        """
        Check if action is explicitly prohibited.

        Args:
            action: Action type (e.g., "delete_constitution")

        Returns:
            True if action is constitutionally prohibited
        """
        return action in self._prohibited_actions

    # ID: is-boundary-violation
    # ID: d3e4f5a6-b7c8-9d0e-1f2a-3b4c5d6e7f8a
    def is_boundary_violation(self, action: str, context: dict[str, Any]) -> list[str]:
        """
        Check if action violates immutable constitutional boundaries.

        Args:
            action: Action type
            context: Execution context (filepath, etc.)

        Returns:
            List of violation messages (empty if no violations)
        """
        violations = []

        if "boundaries" not in self._constitution:
            return violations

        boundaries = self._constitution["boundaries"]
        for principle_id, principle in boundaries.get("principles", {}).items():
            enforcement = principle.get("enforcement", {})
            params = enforcement.get("parameters", {})

            if "patterns_prohibited" in params:
                patterns = params["patterns_prohibited"]
                if isinstance(patterns, list):
                    for pattern in patterns:
                        if self._matches_prohibition_pattern(action, context, pattern):
                            violations.append(
                                f"boundary_violation:{principle_id}:{pattern}"
                            )
                elif isinstance(patterns, str):
                    for pattern in patterns.split():
                        if self._matches_prohibition_pattern(action, context, pattern):
                            violations.append(
                                f"boundary_violation:{principle_id}:{pattern}"
                            )

        return violations

    def _matches_prohibition_pattern(
        self, action: str, context: dict[str, Any], pattern: str
    ) -> bool:
        """
        Check if action/context matches a prohibition pattern.

        Args:
            action: Action type
            context: Execution context
            pattern: Prohibition pattern to match

        Returns:
            True if action/context matches prohibition
        """
        action_lower = action.lower()
        pattern_lower = pattern.lower()
        filepath = context.get("filepath", "")

        # Check for .intent/ modifications
        if "intent" in pattern_lower and ".intent/" in filepath:
            return True

        # Check for governance bypass attempts
        if "bypass" in pattern_lower and "bypass" in action_lower:
            return True

        # Check for audit deletion
        if "audit" in pattern_lower and "delete" in action_lower:
            return True

        return False

    @lru_cache(maxsize=512)
    # ID: classify-risk
    # ID: e4f5a6b7-c8d9-0e1f-2a3b-4c5d6e7f8a9b
    def classify_risk(self, filepath: str, action: str) -> RiskTier:
        """
        Classify operation risk based on path and action.

        Constitutional rule: Returns MAX(path_risk, action_risk)

        Args:
            filepath: Target file path
            action: Action type

        Returns:
            RiskTier classification (ROUTINE, STANDARD, ELEVATED, CRITICAL)
        """
        path_risk = self._classify_path_risk(filepath)
        action_risk = self._classify_action_risk(action)

        # Return maximum risk tier per constitutional rules
        return max(path_risk, action_risk, key=lambda x: x.value)

    def _classify_path_risk(self, filepath: str) -> RiskTier:
        """
        Classify risk based on file path.

        Args:
            filepath: Target file path

        Returns:
            RiskTier based on path patterns
        """
        # .intent/ is always CRITICAL
        if filepath.startswith(".intent/"):
            return RiskTier.CRITICAL

        # Check indexed risk mappings
        for pattern, risk in self._risk_by_path.items():
            if self._match_pattern(filepath, pattern):
                return risk

        # src/ is ELEVATED by default
        if filepath.startswith("src/"):
            return RiskTier.ELEVATED

        # Everything else is STANDARD
        return RiskTier.STANDARD

    def _classify_action_risk(self, action: str) -> RiskTier:
        """
        Classify risk based on action type.

        Args:
            action: Action type

        Returns:
            RiskTier based on action classification
        """
        # Check indexed action risks
        if action in self._risk_by_action:
            return self._risk_by_action[action]

        # Delete operations are ELEVATED
        if action in ["delete", "remove"]:
            return RiskTier.ELEVATED

        # Create/edit are STANDARD
        if action in ["create", "edit", "modify"]:
            return RiskTier.STANDARD

        # Read operations are ROUTINE
        return RiskTier.ROUTINE

    # ID: can-execute-autonomously
    # ID: f5a6b7c8-d9e0-1f2a-3b4c-5d6e7f8a9b0c
    def can_execute_autonomously(
        self, filepath: str, action: str, context: dict[str, Any] | None = None
    ) -> GovernanceDecision:
        """
        Primary governance decision function.

        Determines whether AI can execute action autonomously with rationale.

        This is a Body service capability used by Will layer for decisions.

        Args:
            filepath: Target file path
            action: Action type
            context: Optional execution context

        Returns:
            GovernanceDecision with allowed status, risk tier, and rationale
        """
        context = context or {}
        context["filepath"] = filepath

        # Check for boundary violations (highest priority)
        boundary_violations = self.is_boundary_violation(action, context)
        if boundary_violations:
            return GovernanceDecision(
                allowed=False,
                risk_tier=RiskTier.CRITICAL,
                approval_type=ApprovalType.HUMAN_REVIEW,
                rationale="Constitutional boundary violation",
                violations=boundary_violations,
            )

        # Check if action is explicitly prohibited
        if self.is_action_prohibited(action):
            return GovernanceDecision(
                allowed=False,
                risk_tier=RiskTier.CRITICAL,
                approval_type=ApprovalType.HUMAN_REVIEW,
                rationale=f"Action '{action}' is constitutionally prohibited",
                violations=[f"prohibited_action:{action}"],
            )

        # Classify risk tier
        risk = self.classify_risk(filepath, action)

        # Make decision based on risk tier
        if risk == RiskTier.ROUTINE:
            return GovernanceDecision(
                allowed=True,
                risk_tier=risk,
                approval_type=ApprovalType.AUTONOMOUS,
                rationale="Routine operation, safe for autonomous execution",
                violations=[],
            )
        elif risk == RiskTier.STANDARD:
            return GovernanceDecision(
                allowed=True,
                risk_tier=risk,
                approval_type=ApprovalType.VALIDATION_ONLY,
                rationale="Standard operation, requires constitutional validation",
                violations=[],
            )
        elif risk == RiskTier.ELEVATED:
            return GovernanceDecision(
                allowed=False,
                risk_tier=risk,
                approval_type=ApprovalType.HUMAN_CONFIRMATION,
                rationale="Elevated risk, requires human confirmation",
                violations=[],
            )
        else:  # CRITICAL
            return GovernanceDecision(
                allowed=False,
                risk_tier=risk,
                approval_type=ApprovalType.HUMAN_REVIEW,
                rationale="Critical operation, requires comprehensive human review",
                violations=[],
            )

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """
        Match path against glob pattern.

        Args:
            path: File path to check
            pattern: Glob pattern

        Returns:
            True if path matches pattern
        """
        return fnmatch.fnmatch(path, pattern)

    def _match_any_pattern(self, path: str, patterns: set[str]) -> bool:
        """
        Check if path matches any pattern in set.

        Args:
            path: File path to check
            patterns: Set of glob patterns

        Returns:
            True if path matches any pattern
        """
        return any(self._match_pattern(path, p) for p in patterns)
