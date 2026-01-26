# src/mind/governance/intent_guard.py
"""
Constitutional Enforcement Engine - Main Orchestrator.

IntentGuard is the runtime enforcement layer for CORE's constitutional governance.
It validates all file operations against policies defined in .intent/

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Coordinate validation services
- Thin orchestrator pattern
- Delegates to specialized validators

Architecture:
- Loads rules from IntentRepository (Mind layer)
- Uses RuleConflictDetector for conflict detection
- Delegates path validation to PathValidator
- Delegates code validation to CodeValidator

Extracted responsibilities:
- Conflict detection → RuleConflictDetector
- Path validation → PathValidator
- Code validation → CodeValidator
"""

from __future__ import annotations

from pathlib import Path

from mind.governance.code_validator import CodeValidator
from mind.governance.path_validator import PathValidator
from mind.governance.policy_rule import PolicyRule
from mind.governance.rule_conflict_detector import RuleConflictDetector
from mind.governance.violation_report import (
    ConstitutionalViolationError,
    ViolationReport,
)
from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger
from shared.path_resolver import PathResolver


# Re-export for backward compatibility
__all__ = [
    "ConstitutionalViolationError",
    "IntentGuard",
    "PolicyRule",
    "ViolationReport",
]


logger = getLogger(__name__)


# ID: 4275c592-2725-4fd1-807f-f0d5d83ea78b
class IntentGuard:
    """
    Constitutional enforcement orchestrator.

    Responsibilities:
    - Load constitutional rules from repository
    - Coordinate conflict detection (via RuleConflictDetector)
    - Coordinate path validation (via PathValidator)
    - Coordinate code validation (via CodeValidator)
    """

    def __init__(self, repo_path: Path, path_resolver: PathResolver):
        """
        Initialize IntentGuard with constitutional rules.

        Args:
            repo_path: Absolute path to repository root
            path_resolver: PathResolver for intent_root and path resolution

        Raises:
            GovernanceError: If rule conflicts are detected
        """
        self.repo_path = Path(repo_path).resolve()
        self._path_resolver = path_resolver
        self.intent_root = self._path_resolver.intent_root

        # Load governance from IntentRepository
        self.rules = self._load_rules()

        # Constitutional conflict detection
        conflicts = RuleConflictDetector.detect_conflicts(self.rules)
        if conflicts:
            conflict_details = "\n".join(
                [
                    f"  - Rules '{c['rule1']}' and '{c['rule2']}' both match pattern '{c['pattern']}' "
                    f"with incompatible actions (authority={c['authority']}, action1={c['action1']}, action2={c['action2']})"
                    for c in conflicts
                ]
            )
            raise GovernanceError(
                f"Constitutional rule conflicts detected. Per CORE-Rule-Conflict-Semantics.md, "
                f"conflicts must be resolved in .intent policies, not by runtime precedence ordering:\n{conflict_details}"
            )

        # Sort rules for deterministic evaluation (lexicographic by name)
        self.rules.sort(key=lambda r: r.name)

        # Initialize validators
        self._path_validator = PathValidator(
            self.repo_path, self.intent_root, self.rules
        )

        logger.info(
            "IntentGuard initialized with %s policy rules (0 conflicts detected).",
            len(self.rules),
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    # ID: 9a9a8177-2d56-4d60-8e99-37d551288e14
    def check_transaction(
        self, proposed_paths: list[str]
    ) -> tuple[bool, list[ViolationReport]]:
        """
        Validate a set of proposed file operations.

        Args:
            proposed_paths: List of repo-relative paths (e.g., ["src/main.py"])

        Returns:
            (allowed, violations) - allowed=False if any violations found
        """
        violations = self._path_validator.check_paths(proposed_paths)
        return (len(violations) == 0, violations)

    # ID: 58d875bb-966e-4b82-ab83-66514b9455dc
    async def validate_generated_code(
        self, code: str, pattern_id: str, component_type: str, target_path: str
    ) -> tuple[bool, list[ViolationReport]]:
        """
        Validate generated code against pattern requirements.

        Args:
            code: Generated code content
            pattern_id: Pattern type (e.g., "inspect_pattern", "action_pattern")
            component_type: Component category (for compatibility)
            target_path: Target file path (repo-relative)

        Returns:
            (valid, violations) - valid=False if any violations found
        """
        _ = component_type  # Unused, kept for API compatibility

        violations: list[ViolationReport] = []

        # Path-level validation (hard invariant + rules)
        violations.extend(self._path_validator.check_paths([target_path]))

        # Code-level validation (syntax + pattern checks)
        violations.extend(
            CodeValidator.validate_generated_code(code, pattern_id, target_path)
        )

        return (len(violations) == 0, violations)

    # -------------------------------------------------------------------------
    # Rule Loading
    # -------------------------------------------------------------------------

    def _load_rules(self) -> list[PolicyRule]:
        """
        Load and parse rules from IntentRepository.

        Returns:
            List of PolicyRule objects
        """
        repo = get_intent_repository()
        raw_rules = repo.list_policy_rules()

        rules: list[PolicyRule] = []
        for entry in raw_rules:
            if not isinstance(entry, dict):
                continue
            policy_name = entry.get("policy_name") or "unknown"
            rule_dict = entry.get("rule")
            if isinstance(rule_dict, dict):
                rules.append(PolicyRule.from_dict(rule_dict, source=str(policy_name)))

        return rules
