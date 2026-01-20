# src/body/services/constitutional_validator.py

"""
Constitutional Validator Service

Body layer service that enforces Mind layer governance rules.
Loads rules from .intent/rules/ via IntentRepository and provides
governance decision API for Will layer orchestration.

Mind-Body-Will Separation:
- Mind (.intent/rules/): Defines what is allowed/forbidden
- Body (this service): Provides capability to check rules
- Will: Uses this service to make governed decisions
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


logger = getLogger(__name__)


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
    Body layer service that enforces constitutional governance.

    Loads governance rules from Mind layer (.intent/rules/) via IntentRepository.
    Provides query API for Will layer to make governed decisions.

    Constitutional Compliance:
    - Reads from Mind, never writes
    - Pure execution capability, no decisions
    - Used by Will layer for governance checks
    """

    def __init__(self):
        """Initialize validator by loading rules from IntentRepository."""
        self.intent_repo = get_intent_repository()
        self._rules: dict[str, dict[str, Any]] = {}
        self._critical_paths: set[str] = set()
        self._autonomous_actions: set[str] = set()
        self._prohibited_actions: set[str] = set()
        self._risk_by_path: dict[str, RiskTier] = {}
        self._risk_by_action: dict[str, RiskTier] = {}
        self._load_rules()

    def _load_rules(self):
        """Load all constitutional rules from .intent/rules/ via IntentRepository."""
        logger.info("📜 Loading constitutional governance rules...")

        # Initialize repository indexing
        self.intent_repo.initialize()

        # Access the internal rule index directly
        if not self.intent_repo._rule_index:
            logger.warning("No rules indexed in IntentRepository")
            return

        for rule_id, rule_ref in self.intent_repo._rule_index.items():
            try:
                # RuleRef has: rule_id, policy_id, source_path, content
                rule = rule_ref.content
                self._rules[rule_id] = rule
                self._process_rule(rule_id, rule)
            except Exception as e:
                logger.warning("Failed to load rule %s: %s", rule_id, e)
                continue

        logger.info("✅ Loaded %s constitutional rules", len(self._rules))
        logger.info("   📊 Critical paths: %s", len(self._critical_paths))
        logger.info("   📊 Autonomous actions: %s", len(self._autonomous_actions))
        logger.info("   📊 Prohibited actions: %s", len(self._prohibited_actions))
        logger.info("   📊 Path risk mappings: %s", len(self._risk_by_path))
        logger.info("   📊 Action risk mappings: %s", len(self._risk_by_action))

    def _process_rule(self, rule_id: str, rule: dict[str, Any]):
        """Extract governance information from a rule."""
        statement = rule.get("statement", "")
        enforcement = rule.get("enforcement", "advisory")

        # Extract critical paths (blocking enforcement on .intent/)
        if ".intent" in statement and enforcement == "blocking":
            self._critical_paths.add(".intent/**")

        # Extract autonomous permissions based on rule statements
        if "MUST NOT" in statement or "forbidden" in statement.lower():
            # Extract prohibited actions from rule statement
            if "eval" in statement or "exec" in statement:
                self._prohibited_actions.add("execute_code")
            if "database" in statement.lower() and "Mind" in statement:
                self._prohibited_actions.add("database_access_from_mind")

        # Classify risk based on enforcement strength and authority
        authority = rule.get("authority", "policy")
        if enforcement == "blocking" and authority == "constitution":
            # Constitutional blocking rules are CRITICAL
            if "path" in rule or "scope" in rule:
                scope = rule.get("scope", [])
                if isinstance(scope, dict):
                    scope = scope.get("applies_to", [])
                for pattern in scope if isinstance(scope, list) else [scope]:
                    if pattern:
                        self._risk_by_path[pattern] = RiskTier.CRITICAL
        elif enforcement == "blocking":
            # Regular blocking rules are ELEVATED
            scope = rule.get("scope", [])
            if isinstance(scope, dict):
                scope = scope.get("applies_to", [])
            for pattern in scope if isinstance(scope, list) else [scope]:
                if pattern:
                    self._risk_by_path[pattern] = RiskTier.ELEVATED

        # Actions mentioned in advisory rules are ROUTINE if allowed
        if enforcement == "advisory" and "MAY" in statement:
            # Extract action name from rule_id or statement
            if "." in rule_id:
                action = rule_id.split(".")[-1]
                self._autonomous_actions.add(action)

    # ID: 93e97860-42f9-4605-94f8-1987bcf5343b
    def reload_constitution(self):
        """
        Reload rules from IntentRepository.
        Called by human operators after editing .intent/rules/.
        """
        self._rules.clear()
        self._critical_paths.clear()
        self._autonomous_actions.clear()
        self._prohibited_actions.clear()
        self._risk_by_path.clear()
        self._risk_by_action.clear()

        # Clear LRU caches
        self.is_path_critical.cache_clear()
        self.classify_risk.cache_clear()

        self._load_rules()
        logger.info("🔄 Constitution reloaded from .intent/rules/")

    @lru_cache(maxsize=1024)
    # ID: 8ba370b8-7196-488d-9073-bff294a4d64a
    def is_path_critical(self, filepath: str) -> bool:
        """Check if path is critical (requires human approval)."""
        # .intent/ is always critical
        if filepath.startswith(".intent/"):
            return True

        # Check against indexed critical paths
        for pattern in self._critical_paths:
            if self._match_pattern(filepath, pattern):
                return True

        return False

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
        """
        Check if action violates immutable boundaries.

        Boundary violations include:
        - Writing to .intent/ directory
        - Bypassing governance checks
        - Modifying audit trails
        """
        violations = []
        filepath = context.get("filepath", "")

        # Critical: Cannot write to .intent/
        if filepath.startswith(".intent/") and action in ["create", "edit", "delete"]:
            violations.append("boundary_violation:constitution_immutable:.intent/")

        # Check for governance bypass attempts
        if "bypass" in action.lower() or "override" in action.lower():
            violations.append("boundary_violation:no_governance_bypass")

        return violations

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
        """Classify risk based on action type."""
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

    # ID: 60939e24-a359-4396-9ad9-18bdd2ad426d
    def can_execute_autonomously(
        self, filepath: str, action: str, context: dict[str, Any] | None = None
    ) -> GovernanceDecision:
        """
        Primary governance decision function.
        Returns whether AI can execute action autonomously with rationale.

        This is a Body service capability used by Will layer for decisions.
        """
        context = context or {}
        context["filepath"] = filepath

        # Check boundary violations first (highest priority)
        boundary_violations = self.is_boundary_violation(action, context)
        if boundary_violations:
            return GovernanceDecision(
                allowed=False,
                risk_tier=RiskTier.CRITICAL,
                approval_type=ApprovalType.HUMAN_REVIEW,
                rationale="Constitutional boundary violation",
                violations=boundary_violations,
            )

        # Check prohibited actions
        if self.is_action_prohibited(action):
            return GovernanceDecision(
                allowed=False,
                risk_tier=RiskTier.CRITICAL,
                approval_type=ApprovalType.HUMAN_REVIEW,
                rationale=f"Action '{action}' is constitutionally prohibited",
                violations=[f"prohibited_action:{action}"],
            )

        # Classify risk and determine approval requirements
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
        import fnmatch

        return fnmatch.fnmatch(path, pattern)


# Singleton instance
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
    """Reload constitution. Called by operators after editing .intent/rules/."""
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
        ("src/body/services/constitutional_validator.py", "format_code"),
        (".intent/rules/architecture/governance_basics.json", "edit_file"),
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
