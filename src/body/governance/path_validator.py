# src/body/governance/path_validator.py
# ID: 41eba414-1d91-417c-827b-d897cb9758e7

"""
Path Validator - Body Layer Enforcement Service.

CONSTITUTIONAL PROMOTION (v2.7):
- Resolved LEGACY debt: Removed hardcoded 'no_write_intent'.
- Mind-Aligned: Now enforces 'governance.constitution.read_only' from the Mind.
- Rule-Driven: Violation messages are now sourced from the provided PolicyRule list.
"""

from __future__ import annotations

from pathlib import Path

from body.governance.engine_dispatcher import EngineDispatcher
from mind.governance.policy_rule import PolicyRule
from mind.governance.violation_report import ViolationReport
from shared.logger import getLogger
from shared.models.constitutional_validation import ConstitutionalValidationResult


logger = getLogger(__name__)


# ID: 14def661-c022-473c-8069-c127e5868fe6
class PathValidator:
    """
    Validates file paths against constitutional rules.

    Responsibilities:
    - Pattern matching (glob-based)
    - Rule application (engine dispatch or simple actions)
    - Hard invariant enforcement (.intent writes)
    """

    # Aligned with .intent/rules/architecture/governance_basics.json
    _READ_ONLY_RULE_ID = "governance.constitution.read_only"

    def __init__(self, repo_path: Path, intent_root: Path, rules: list[PolicyRule]):
        """
        Initialize path validator.

        Args:
            repo_path: Repository root (absolute)
            intent_root: Intent directory (absolute)
            rules: Sorted list of policy rules
        """
        self.repo_path = repo_path.resolve()
        self.intent_root = intent_root.resolve()
        self.rules = rules

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    # ID: 5a61b7ff-d43c-4ae7-820c-a26997d76937
    def check_paths(self, proposed_paths: list[str]) -> ConstitutionalValidationResult:
        """
        Validate a set of proposed file operations.
        """
        violations: list[ViolationReport] = []

        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()
            violations.extend(self._check_single_path(abs_path, path_str))

        return ConstitutionalValidationResult(
            is_valid=len(violations) == 0, violations=violations, source="PathValidator"
        )

    def _check_single_path(self, path: Path, path_str: str) -> list[ViolationReport]:
        """
        Enforce constitutional rules against a single path.
        """
        violations: list[ViolationReport] = []

        # 1. THE CONSTITUTIONAL INVARIANT (Hard Guard)
        hard = self._check_no_write_intent(path, path_str)
        if hard is not None:
            violations.append(hard)
            return violations  # Stop checking if hard invariant is broken

        # 2. POLICY RULES (Dynamic Guard)
        violations.extend(self._check_policy_rules(path, path_str))

        return violations

    # -------------------------------------------------------------------------
    # Hard Invariant
    # -------------------------------------------------------------------------

    def _check_no_write_intent(
        self, abs_path: Path, rel_path_str: str
    ) -> ViolationReport | None:
        """
        HARD INVARIANT: .intent/** is never writable by CORE.
        Linked to Sovereign Rule: governance.constitution.read_only
        """
        try:
            if abs_path == self.intent_root or self.intent_root in abs_path.parents:
                # Find the actual rule in our rules list to get the authoritative text
                rule = next(
                    (r for r in self.rules if r.name == self._READ_ONLY_RULE_ID), None
                )

                return ViolationReport(
                    rule_name=self._READ_ONLY_RULE_ID,
                    path=rel_path_str,
                    message=(
                        rule.description
                        if rule
                        else "Writes to .intent/ are forbidden."
                    ),
                    severity="error",
                    suggested_fix="Route changes through non-CORE mechanism.",
                    source_policy="constitution_hard_invariant",
                )
        except Exception as e:
            logger.error(
                "Error enforcing .intent hard invariant for %s: %s", rel_path_str, e
            )
            return ViolationReport(
                rule_name=self._READ_ONLY_RULE_ID,
                path=rel_path_str,
                message="Failed to evaluate .intent boundary. Fail-closed: forbidden.",
                severity="error",
                source_policy="constitution_hard_invariant",
            )

        return None

    # -------------------------------------------------------------------------
    # Policy Rule Enforcement
    # -------------------------------------------------------------------------

    def _check_policy_rules(self, path: Path, path_str: str) -> list[ViolationReport]:
        """
        Apply all matching constitutional rules to a path.
        """
        violations: list[ViolationReport] = []

        for rule in self.rules:
            # We already handled the Hard Invariant specifically above
            if rule.name == self._READ_ONLY_RULE_ID:
                continue

            try:
                if not self._matches_pattern(path_str, rule.pattern):
                    continue

                # Apply rule action (engine dispatch or simple deny/warn)
                violations.extend(self._apply_rule_action(rule, path, path_str))

            except Exception as e:
                logger.error(
                    "Error applying rule '%s' to %s: %s", rule.name, path_str, e
                )

        return violations

    def _apply_rule_action(
        self, rule: PolicyRule, path: Path, path_str: str
    ) -> list[ViolationReport]:
        """
        Execute rule enforcement.
        """
        if rule.engine:
            return EngineDispatcher.invoke_engine(rule, path, path_str)

        if rule.action == "deny" or rule.severity in ("blocking", "error"):
            return [
                ViolationReport(
                    rule_name=rule.name,
                    path=path_str,
                    message=rule.description,
                    severity="error",
                    source_policy=rule.source_policy,
                )
            ]

        if rule.action == "warn":
            logger.warning("Policy warning for %s: %s", path_str, rule.description)

        return []

    @staticmethod
    def _matches_pattern(path: str, pattern: str) -> bool:
        if not pattern:
            return False
        return Path(path).match(pattern)
