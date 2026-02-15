# src/mind/governance/path_validator.py

"""
Path Validator - File Path Validation Logic

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Validate file paths against rules
- No rule loading, no conflict detection
- Pure validation logic

Extracted from IntentGuard to separate path validation concerns.
"""

from __future__ import annotations

from pathlib import Path

from body.governance.engine_dispatcher import EngineDispatcher
from mind.governance.policy_rule import PolicyRule
from mind.governance.violation_report import ViolationReport
from shared.logger import getLogger
from shared.models.constitutional_validation import ConstitutionalValidationResult


logger = getLogger(__name__)


# ID: 41eba414-1d91-417c-827b-d897cb9758e7
# ID: fdd5f030-9cd6-4138-b11e-e88809a301aa
class PathValidator:
    """
    Validates file paths against constitutional rules.

    Responsibilities:
    - Pattern matching (glob-based)
    - Rule application (engine dispatch or simple actions)
    - Hard invariant enforcement (.intent writes)
    """

    _NO_WRITE_INTENT_RULE = "no_write_intent"

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

    # ID: 449c0253-1cf7-4534-b8a6-deb5df20867f
    # ID: 501cc08d-6965-47a8-a9e9-930e84083d3a
    def check_paths(self, proposed_paths: list[str]) -> ConstitutionalValidationResult:
        """
        Validate a set of proposed file operations.

        Args:
            proposed_paths: List of repo-relative paths

        Returns:
            List of violations (empty if all valid)
        """
        violations: list[ViolationReport] = []

        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()
            violations.extend(self._check_single_path(abs_path, path_str))

        return ConstitutionalValidationResult(
            is_valid=len(violations) == 0, violations=violations, source="PathValidator"
        )

    # ID: d3929a5f-72a8-478f-be8d-27a20bc6c7fe
    # ID: 03074b9a-c174-4ffb-9a2b-894e7a0b73f2
    def _check_single_path(self, path: Path, path_str: str) -> list[ViolationReport]:
        """
        Enforce constitutional rules against a single path.

        Args:
            path: Absolute path
            path_str: Repo-relative path string

        Returns:
            List of violations
        """
        violations: list[ViolationReport] = []

        # Hard invariant (defense in depth)
        hard = self._check_no_write_intent(path, path_str)
        if hard is not None:
            violations.append(hard)
            return violations

        # Policy rules with engine dispatch
        violations.extend(self._check_policy_rules(path, path_str))

        return violations

    # -------------------------------------------------------------------------
    # Hard Invariant
    # -------------------------------------------------------------------------

    # ID: 0d39906a-e7e5-4810-8158-e64867f347e4
    # ID: 799fddd4-f50d-40a1-a659-e52f8e58f791
    def _check_no_write_intent(
        self, abs_path: Path, rel_path_str: str
    ) -> ViolationReport | None:
        """
        HARD INVARIANT: .intent/** is never writable by CORE.

        This rule has no bypass, no emergency override, no exceptions.

        Args:
            abs_path: Absolute file path
            rel_path_str: Repository-relative path

        Returns:
            ViolationReport if path is under .intent, None otherwise
        """
        try:
            if abs_path == self.intent_root or self.intent_root in abs_path.parents:
                return ViolationReport(
                    rule_name=self._NO_WRITE_INTENT_RULE,
                    path=rel_path_str,
                    message=(
                        f"Direct write to '{rel_path_str}' is forbidden. "
                        "CORE must never write to .intent/**."
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
                rule_name=self._NO_WRITE_INTENT_RULE,
                path=rel_path_str,
                message="Failed to evaluate .intent boundary. Fail-closed: forbidden.",
                severity="error",
                source_policy="constitution_hard_invariant",
            )

        return None

    # -------------------------------------------------------------------------
    # Policy Rule Enforcement
    # -------------------------------------------------------------------------

    # ID: 8eecf9da-cd69-453e-aa1d-cb8004cfe46d
    # ID: 72cab840-244f-4ba5-947e-aaf052de1f44
    def _check_policy_rules(self, path: Path, path_str: str) -> list[ViolationReport]:
        """
        Apply all matching constitutional rules to a path.

        Rules are evaluated in deterministic order (sorted by name).
        Engine-based rules are dispatched to EngineDispatcher.

        Args:
            path: Absolute file path
            path_str: Repository-relative path

        Returns:
            List of violations
        """
        violations: list[ViolationReport] = []

        for rule in self.rules:
            try:
                # Pattern matching (glob-based)
                if not self._matches_pattern(path_str, rule.pattern):
                    continue

                # Apply rule action (engine dispatch or simple deny/warn)
                violations.extend(self._apply_rule_action(rule, path, path_str))

            except Exception as e:
                logger.error(
                    "Error applying rule '%s' to %s: %s", rule.name, path_str, e
                )

        return violations

    # ID: 3dd711af-9f19-4126-8925-507f9a15ff3d
    # ID: 9854e4fa-7371-491c-8a68-bc166cc80382
    def _apply_rule_action(
        self, rule: PolicyRule, path: Path, path_str: str
    ) -> list[ViolationReport]:
        """
        Execute rule enforcement.

        Dispatches to engine if rule specifies one, otherwise applies
        simple deny/warn action.

        Args:
            rule: Policy rule to apply
            path: Absolute file path
            path_str: Repository-relative path

        Returns:
            List of violations
        """
        # ENGINE DISPATCH: Constitutional rule specifies engine
        if rule.engine:
            return EngineDispatcher.invoke_engine(rule, path, path_str)

        # LEGACY: Simple deny/warn actions (no engine)
        if rule.action == "deny":
            return [
                ViolationReport(
                    rule_name=rule.name,
                    path=path_str,
                    message=f"Rule '{rule.name}' violation: {rule.description}",
                    severity=rule.severity,
                    source_policy=rule.source_policy,
                )
            ]

        if rule.action == "warn":
            logger.warning("Policy warning for %s: %s", path_str, rule.description)

        return []

    # ID: ceda57fc-5f4b-4c44-9581-e5fd27e28880
    # ID: f5a96cb9-475e-4f44-8c74-d2ae938ad289
    @staticmethod
    def _matches_pattern(path: str, pattern: str) -> bool:
        """
        Glob-based pattern matching.

        Args:
            path: File path to check
            pattern: Glob pattern

        Returns:
            True if path matches pattern
        """
        if not pattern:
            return False
        return Path(path).match(pattern)
