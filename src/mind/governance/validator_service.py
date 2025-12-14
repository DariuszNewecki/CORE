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
        authority_file = self.constitution_path / "authority.yaml"
        if authority_file.exists():
            self._constitution["authority"] = yaml.safe_load(authority_file.read_text())
        boundaries_file = self.constitution_path / "boundaries.yaml"
        if boundaries_file.exists():
            self._constitution["boundaries"] = yaml.safe_load(
                boundaries_file.read_text()
            )
        risk_file = self.constitution_path / "risk_classification.yaml"
        if risk_file.exists():
            self._constitution["risk"] = yaml.safe_load(risk_file.read_text())
        logger.info("✅ Constitution loaded: %s documents", len(self._constitution))
        self._build_lookup_tables()

    def _build_lookup_tables(self):
        """Build fast lookup tables from constitutional principles."""
        self._critical_paths: set[str] = set()
        self._autonomous_actions: set[str] = set()
        self._prohibited_actions: set[str] = set()
        self._risk_by_path: dict[str, RiskTier] = {}
        self._risk_by_action: dict[str, RiskTier] = {}
        if "authority" in self._constitution:
            auth = self._constitution["authority"]
            for principle_id, principle in auth.get("principles", {}).items():
                scope = principle.get("scope", [])
                enforcement = principle.get("enforcement", {})
                params = enforcement.get("parameters", {})
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
                if "patterns" in params:
                    patterns = params["patterns"]
                    if isinstance(patterns, list):
                        for pattern in patterns:
                            if (
                                "critical" in principle_id
                                or "constitutional" in principle_id
                            ):
                                self._critical_paths.add(pattern)
        if "risk" in self._constitution:
            risk = self._constitution["risk"]
            for principle_id, principle in risk.get("principles", {}).items():
                enforcement = principle.get("enforcement", {})
                params = enforcement.get("parameters", {})
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
        logger.info("   📊 Indexed: %s critical paths", len(self._critical_paths))
        logger.info(
            "   📊 Indexed: %s autonomous actions", len(self._autonomous_actions)
        )
        logger.info("   📊 Indexed: %s path risk mappings", len(self._risk_by_path))
        logger.info("   📊 Indexed: %s action risk mappings", len(self._risk_by_action))

    # ID: 93e97860-42f9-4605-94f8-1987bcf5343b
    def reload_constitution(self):
        """Reload constitution from disk. Called by human operators after edits."""
        self._constitution.clear()
        self._load_constitution()
        self.is_path_critical.cache_clear()
        self.classify_risk.cache_clear()
        logger.info("🔄 Constitution reloaded")

    @lru_cache(maxsize=1024)
    # ID: 8ba370b8-7196-488d-9073-bff294a4d64a
    def is_path_critical(self, filepath: str) -> bool:
        """Check if path is in critical_paths requiring human approval."""
        return self._match_any_pattern(filepath, self._critical_paths)

    @lru_cache(maxsize=1024)
    # ID: bc1c3a49-105e-443f-896e-46099ba1c274
    def is_action_autonomous(self, action: str) -> bool:
        """Check if action is allowed for autonomous execution."""
        return action in self._autonomous_actions

    @lru_cache(maxsize=1024)
    # ID: 53a1a9ff-03d0-49bf-9857-325b4b94b677
    def is_action_prohibited(self, action: str) -> bool:
        """Check if action is explicitly prohibited."""
        return action in self._prohibited_actions

    # ID: bd51dd23-d36c-4eb8-8dc8-df8c6214fb0d
    def is_boundary_violation(self, action: str, context: dict[str, Any]) -> list[str]:
        """Check if action violates immutable boundaries."""
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
        """Check if action/context matches a prohibition pattern."""
        action_lower = action.lower()
        pattern_lower = pattern.lower()
        filepath = context.get("filepath", "")
        if "intent" in pattern_lower and ".intent/" in filepath:
            return True
        if "bypass" in pattern_lower and "bypass" in action_lower:
            return True
        if "audit" in pattern_lower and "delete" in action_lower:
            return True
        return False

    @lru_cache(maxsize=512)
    # ID: 18fa2148-c919-4799-88ed-13cb61516481
    def classify_risk(self, filepath: str, action: str) -> RiskTier:
        """
        Classify operation risk based on path and action.
        Returns MAX(path_risk, action_risk) per constitutional rules.
        """
        path_risk = self._classify_path_risk(filepath)
        action_risk = self._classify_action_risk(action)
        return max(path_risk, action_risk, key=lambda x: x.value)

    def _classify_path_risk(self, filepath: str) -> RiskTier:
        """Classify risk based on file path."""
        for pattern, risk in self._risk_by_path.items():
            if self._match_pattern(filepath, pattern):
                return risk
        return RiskTier.ELEVATED

    def _classify_action_risk(self, action: str) -> RiskTier:
        """Classify risk based on action type."""
        if action in self._risk_by_action:
            return self._risk_by_action[action]
        return RiskTier.STANDARD

    # ID: 60939e24-a359-4396-9ad9-18bdd2ad426d
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
        boundary_violations = self.is_boundary_violation(action, context)
        if boundary_violations:
            return GovernanceDecision(
                allowed=False,
                risk_tier=RiskTier.CRITICAL,
                approval_type=ApprovalType.HUMAN_REVIEW,
                rationale="Constitutional boundary violation",
                violations=boundary_violations,
            )
        if self.is_action_prohibited(action):
            return GovernanceDecision(
                allowed=False,
                risk_tier=RiskTier.CRITICAL,
                approval_type=ApprovalType.HUMAN_REVIEW,
                rationale=f"Action '{action}' is constitutionally prohibited",
                violations=[f"prohibited_action:{action}"],
            )
        risk = self.classify_risk(filepath, action)
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
        else:
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


_validator_instance: ConstitutionalValidator | None = None


# ID: bb0cd5d6-4e09-4531-9da1-e3ebc8bbb3ac
def get_validator() -> ConstitutionalValidator:
    """Get or create global validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ConstitutionalValidator()
    return _validator_instance


# ID: 233e79f4-3e4e-410c-a1e6-6e15d2e1ed69
def reload_constitution():
    """Reload constitution. Called by operators after editing .intent/."""
    validator = get_validator()
    validator.reload_constitution()


# ID: 68b55dc7-ae11-43c8-8d00-86c7bd4a6a28
def is_path_critical(filepath: str) -> bool:
    """Check if path requires human approval."""
    return get_validator().is_path_critical(filepath)


# ID: 066efefd-373f-49ce-8b25-fce30fbd3447
def is_action_autonomous(action: str) -> bool:
    """Check if action is allowed autonomously."""
    return get_validator().is_action_autonomous(action)


# ID: af479369-925b-452f-b59f-5167f9280411
def classify_risk(filepath: str, action: str) -> RiskTier:
    """Classify operation risk."""
    return get_validator().classify_risk(filepath, action)


# ID: 9f1f43b2-fb0c-4728-bec8-32a245d6f51b
def can_execute_autonomously(
    filepath: str, action: str, context: dict[str, Any] | None = None
) -> GovernanceDecision:
    """Primary governance check - can AI execute this autonomously?"""
    return get_validator().can_execute_autonomously(filepath, action, context)


if __name__ == "__main__":
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
        logger.info("   Risk: %s", decision.risk_tier.name)
        logger.info("   Allowed: %s", decision.allowed)
        logger.info("   Approval: %s", decision.approval_type.value)
        logger.info("   Rationale: %s", decision.rationale)
        if decision.violations:
            logger.info("   Violations: %s", decision.violations)
    logger.info("\n" + "=" * 80)
