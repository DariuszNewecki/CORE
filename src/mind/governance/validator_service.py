# src/mind/governance/validator_service.py

"""
Constitutional Validator Service
Loads governance rules from .intent/charter/constitution/ and provides query API.
This is the Body layer that enforces Mind layer policies.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)

import fnmatch
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


# ID: efb81ac5-5520-4cf3-8292-3b6bf049cb24
class RiskTier(Enum):
    """Risk classification for operations."""

    ROUTINE = 1
    STANDARD = 3
    ELEVATED = 7
    CRITICAL = 10


# ID: d761610e-b880-4838-85cf-50a9ca2266a7
class ApprovalType(Enum):
    """Approval mechanism required."""

    AUTONOMOUS = "autonomous"
    VALIDATION_ONLY = "validation_only"
    HUMAN_CONFIRMATION = "human_confirmation"
    HUMAN_REVIEW = "human_review"


@dataclass
# ID: 3ea9a7f3-3cb9-43bd-af28-a9129e5386c7
class GovernanceDecision:
    """Result of governance validation."""

    allowed: bool
    risk_tier: RiskTier
    approval_type: ApprovalType
    rationale: str
    violations: list[str]


# ID: 1d4ff5ea-dae6-4eed-b576-7418c71480a9
class ConstitutionalValidator:
    """
    Enforces constitutional governance by validating operations against Mind layer.
    Loaded once at startup, queried many times by Will layer.
    """

    def __init__(self, constitution_path: Path = Path(".intent/charter/constitution")):
        self.constitution_path = constitution_path
        self._constitution: dict[str, Any] = {}
        self._load_constitution()

    def _load_constitution(self):
        """Load all constitutional YAML files into memory."""
        logger.info("📜 Loading constitutional governance...")

        # Load authority rules
        authority_file = self.constitution_path / "authority.yaml"
        if authority_file.exists():
            self._constitution["authority"] = yaml.safe_load(authority_file.read_text())

        # Load boundaries
        boundaries_file = self.constitution_path / "boundaries.yaml"
        if boundaries_file.exists():
            self._constitution["boundaries"] = yaml.safe_load(
                boundaries_file.read_text()
            )

        # Load risk classification
        risk_file = self.constitution_path / "risk_classification.yaml"
        if risk_file.exists():
            self._constitution["risk"] = yaml.safe_load(risk_file.read_text())

        logger.info(f"✅ Constitution loaded: {len(self._constitution)} documents")
        self._build_lookup_tables()

    def _build_lookup_tables(self):
        """Build fast lookup tables from constitutional principles."""
        self._critical_paths: set[str] = set()
        self._autonomous_actions: set[str] = set()
        self._prohibited_actions: set[str] = set()
        self._risk_by_path: dict[str, RiskTier] = {}
        self._risk_by_action: dict[str, RiskTier] = {}

        # Extract from authority document
        if "authority" in self._constitution:
            auth = self._constitution["authority"]
            for principle_id, principle in auth.get("principles", {}).items():
                scope = principle.get("scope", [])
                enforcement = principle.get("enforcement", {})
                params = enforcement.get("parameters", {})

                # Build action lists (handle both list and space-separated string formats)
                if "actions_allowed" in params:
                    actions = params["actions_allowed"]
                    if isinstance(actions, list):
                        self._autonomous_actions.update(actions)
                    elif isinstance(actions, str):
                        self._autonomous_actions.update(actions.split())

                if "actions_prohibited" in params:
                    actions = params["actions_prohibited"]
                    if isinstance(actions, list):
                        self._prohibited_actions.update(actions)
                    elif isinstance(actions, str):
                        self._prohibited_actions.update(actions.split())

                # Build path lists from patterns parameter (list format)
                if "patterns" in params:
                    patterns = params["patterns"]
                    if isinstance(patterns, list):
                        for pattern in patterns:
                            if (
                                "critical" in principle_id
                                or "constitutional" in principle_id
                            ):
                                self._critical_paths.add(pattern)

        # Extract from risk document
        if "risk" in self._constitution:
            risk = self._constitution["risk"]
            for principle_id, principle in risk.get("principles", {}).items():
                enforcement = principle.get("enforcement", {})
                params = enforcement.get("parameters", {})

                # Handle space-separated string format for paths
                if "critical" in params:
                    paths = params["critical"]
                    if isinstance(paths, str):
                        for path in paths.split():
                            self._risk_by_path[path] = RiskTier.CRITICAL
                    elif isinstance(paths, list):
                        for path in paths:
                            self._risk_by_path[path] = RiskTier.CRITICAL

                if "elevated" in params:
                    paths = params["elevated"]
                    if isinstance(paths, str):
                        for path in paths.split():
                            self._risk_by_path[path] = RiskTier.ELEVATED
                    elif isinstance(paths, list):
                        for path in paths:
                            self._risk_by_path[path] = RiskTier.ELEVATED

                if "standard" in params:
                    paths = params["standard"]
                    if isinstance(paths, str):
                        for path in paths.split():
                            self._risk_by_path[path] = RiskTier.STANDARD
                    elif isinstance(paths, list):
                        for path in paths:
                            self._risk_by_path[path] = RiskTier.STANDARD

                if "routine" in params:
                    paths = params["routine"]
                    if isinstance(paths, str):
                        for path in paths.split():
                            self._risk_by_path[path] = RiskTier.ROUTINE
                    elif isinstance(paths, list):
                        for path in paths:
                            self._risk_by_path[path] = RiskTier.ROUTINE

                # Handle space-separated string format for actions
                if "actions_critical" in params or "critical" in params:
                    actions_key = (
                        "actions_critical"
                        if "actions_critical" in params
                        else "critical"
                    )
                    actions = params[actions_key]
                    if isinstance(actions, str):
                        for action in actions.split():
                            self._risk_by_action[action] = RiskTier.CRITICAL
                    elif isinstance(actions, list):
                        for action in actions:
                            self._risk_by_action[action] = RiskTier.CRITICAL

                if "actions_elevated" in params or "elevated" in params:
                    actions_key = (
                        "actions_elevated"
                        if "actions_elevated" in params
                        else "elevated"
                    )
                    actions = params[actions_key]
                    if isinstance(actions, str):
                        for action in actions.split():
                            self._risk_by_action[action] = RiskTier.ELEVATED
                    elif isinstance(actions, list):
                        for action in actions:
                            self._risk_by_action[action] = RiskTier.ELEVATED

                if "actions_standard" in params or "standard" in params:
                    actions_key = (
                        "actions_standard"
                        if "actions_standard" in params
                        else "standard"
                    )
                    actions = params[actions_key]
                    if isinstance(actions, str):
                        for action in actions.split():
                            self._risk_by_action[action] = RiskTier.STANDARD
                    elif isinstance(actions, list):
                        for action in actions:
                            self._risk_by_action[action] = RiskTier.STANDARD

                if "actions_routine" in params or "routine" in params:
                    actions_key = (
                        "actions_routine" if "actions_routine" in params else "routine"
                    )
                    actions = params[actions_key]
                    if isinstance(actions, str):
                        for action in actions.split():
                            self._risk_by_action[action] = RiskTier.ROUTINE
                    elif isinstance(actions, list):
                        for action in actions:
                            self._risk_by_action[action] = RiskTier.ROUTINE

        logger.info(f"   📊 Indexed: {len(self._critical_paths)} critical paths")
        logger.info(
            f"   📊 Indexed: {len(self._autonomous_actions)} autonomous actions"
        )
        logger.info(f"   📊 Indexed: {len(self._risk_by_path)} path risk mappings")
        logger.info(f"   📊 Indexed: {len(self._risk_by_action)} action risk mappings")

    # ID: 5e7fcaac-7b10-4ef5-a99d-8ec84bdb9ac6
    def reload_constitution(self):
        """Reload constitution from disk. Called by human operators after edits."""
        self._constitution.clear()
        self._load_constitution()
        # Clear all cached results
        self.is_path_critical.cache_clear()
        self.classify_risk.cache_clear()
        logger.info("🔄 Constitution reloaded")

    @lru_cache(maxsize=1024)
    # ID: e2eda695-290e-4e2a-8f57-9231cd8b4db5
    def is_path_critical(self, filepath: str) -> bool:
        """Check if path is in critical_paths requiring human approval."""
        return self._match_any_pattern(filepath, self._critical_paths)

    @lru_cache(maxsize=1024)
    # ID: aa693786-c317-4dcf-9ddf-ccf1b6a337c0
    def is_action_autonomous(self, action: str) -> bool:
        """Check if action is allowed for autonomous execution."""
        return action in self._autonomous_actions

    @lru_cache(maxsize=1024)
    # ID: eeb87bf4-2092-44ae-80da-ec5ae5adbde6
    def is_action_prohibited(self, action: str) -> bool:
        """Check if action is explicitly prohibited."""
        return action in self._prohibited_actions

    # ID: 746e5c0e-cf3a-42ab-bce1-1185e757b256
    def is_boundary_violation(self, action: str, context: dict[str, Any]) -> list[str]:
        """Check if action violates immutable boundaries."""
        violations = []

        if "boundaries" not in self._constitution:
            return violations

        boundaries = self._constitution["boundaries"]

        # Check each boundary principle
        for principle_id, principle in boundaries.get("principles", {}).items():
            enforcement = principle.get("enforcement", {})
            params = enforcement.get("parameters", {})

            # Check prohibited patterns (handle both list and space-separated)
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
        """Check if action/context matches a prohibition pattern."""
        action_lower = action.lower()
        pattern_lower = pattern.lower()
        filepath = context.get("filepath", "")

        # Pattern matching rules
        if "intent" in pattern_lower and ".intent/" in filepath:
            return True

        if "bypass" in pattern_lower and "bypass" in action_lower:
            return True

        if "audit" in pattern_lower and "delete" in action_lower:
            return True

        return False

    @lru_cache(maxsize=512)
    # ID: 31ffffdf-13bd-47c4-93cf-a87793074137
    def classify_risk(self, filepath: str, action: str) -> RiskTier:
        """
        Classify operation risk based on path and action.
        Returns MAX(path_risk, action_risk) per constitutional rules.
        """
        path_risk = self._classify_path_risk(filepath)
        action_risk = self._classify_action_risk(action)

        # Return maximum risk (more conservative)
        return max(path_risk, action_risk, key=lambda x: x.value)

    def _classify_path_risk(self, filepath: str) -> RiskTier:
        """Classify risk based on file path."""
        # Check against indexed patterns
        for pattern, risk in self._risk_by_path.items():
            if self._match_pattern(filepath, pattern):
                return risk

        # Default to elevated if unknown
        return RiskTier.ELEVATED

    def _classify_action_risk(self, action: str) -> RiskTier:
        """Classify risk based on action type."""
        # Direct lookup
        if action in self._risk_by_action:
            return self._risk_by_action[action]

        # Default to standard if unknown
        return RiskTier.STANDARD

    # ID: 9d640d49-cc9b-47bd-b292-73a1da6ce1e3
    def can_execute_autonomously(
        self, filepath: str, action: str, context: dict[str, Any] | None = None
    ) -> GovernanceDecision:
        """
        Primary governance decision function.
        Returns whether AI can execute action autonomously with rationale.
        """
        context = context or {}
        context["filepath"] = filepath
        violations = []

        # Check boundary violations first
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

        # Classify risk
        risk = self.classify_risk(filepath, action)

        # Determine approval type based on risk
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
        """Match path against glob pattern."""
        return fnmatch.fnmatch(path, pattern)

    def _match_any_pattern(self, path: str, patterns: set[str]) -> bool:
        """Check if path matches any pattern in set."""
        return any(self._match_pattern(path, pattern) for pattern in patterns)


# ============================================================================
# GLOBAL INSTANCE (Singleton Pattern)
# ============================================================================

_validator_instance: ConstitutionalValidator | None = None


# ID: 426b58b8-1127-4c8d-ab35-d6ad8f144a0c
def get_validator() -> ConstitutionalValidator:
    """Get or create global validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ConstitutionalValidator()
    return _validator_instance


# ID: 19c0136c-c8f0-4fef-b351-d42e5be7b853
def reload_constitution():
    """Reload constitution. Called by operators after editing .intent/."""
    validator = get_validator()
    validator.reload_constitution()


# ============================================================================
# CONVENIENCE API (What AI Agents Call)
# ============================================================================


# ID: 7e94fb14-f39f-4ce9-9f9a-4a3681d12338
def is_path_critical(filepath: str) -> bool:
    """Check if path requires human approval."""
    return get_validator().is_path_critical(filepath)


# ID: 220518e6-387e-4abf-90ac-3489439b5011
def is_action_autonomous(action: str) -> bool:
    """Check if action is allowed autonomously."""
    return get_validator().is_action_autonomous(action)


# ID: 6ac4e5db-b661-4814-b8c1-9766ccbe167b
def classify_risk(filepath: str, action: str) -> RiskTier:
    """Classify operation risk."""
    return get_validator().classify_risk(filepath, action)


# ID: cb13877d-4655-45e7-9296-706834294bae
def can_execute_autonomously(
    filepath: str, action: str, context: dict[str, Any] | None = None
) -> GovernanceDecision:
    """Primary governance check - can AI execute this autonomously?"""
    return get_validator().can_execute_autonomously(filepath, action, context)


# ============================================================================
# TESTING/DEBUG
# ============================================================================

if __name__ == "__main__":
    # Test the validator
    validator = get_validator()

    logger.info("\n" + "=" * 80)
    logger.info("CONSTITUTIONAL VALIDATOR TEST")
    logger.info("=" * 80)

    test_cases = [
        ("src/body/commands/fix.py", "fix_docstring"),
        ("src/mind/governance/validator_service.py", "format_code"),
        (".intent/charter/constitution/authority.yaml", "edit_file"),
        ("src/body/services/database.py", "schema_migration"),
        ("docs/README.md", "update_docs"),
        ("tests/test_core.py", "generate_tests"),
        ("src/body/core/database.py", "refactoring"),
    ]

    for filepath, action in test_cases:
        decision = can_execute_autonomously(filepath, action, {"filepath": filepath})
        logger.info("\n📋 Action: %s", action)
        logger.info("   Path: %s", filepath)
        logger.info(f"   Risk: {decision.risk_tier.name}")
        logger.info(f"   Allowed: {decision.allowed}")
        logger.info(f"   Approval: {decision.approval_type.value}")
        logger.info(f"   Rationale: {decision.rationale}")
        if decision.violations:
            logger.info(f"   Violations: {decision.violations}")

    logger.info("\n" + "=" * 80)
