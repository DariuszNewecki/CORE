# src/body/governance/intent_guard.py
"""
Constitutional Enforcement Engine - Main Orchestrator.

MOVED FROM MIND TO BODY (Constitutional Compliance):
IntentGuard performs EXECUTION logic (validation, enforcement decisions).
Mind layer defines law (.intent/), Body layer enforces it.

IntentGuard is the runtime enforcement layer for CORE's constitutional governance.
It validates all file operations against policies defined in .intent/

Architecture:
- Loads rules from IntentRepository (Mind layer - human-authored)
- Applies precedence-based rule ordering
- Dispatches to engines (AST, regex, glob, workflow) for verification
- Enforces hard invariants (e.g., no .intent writes)
- Supports emergency override (bypass policy, never .intent)

Wiring:
- FileHandler calls IntentGuard before mutations
- Engines are invoked via EngineDispatcher
- Pattern validators provide backward compatibility during migration
"""

from __future__ import annotations

import ast
from pathlib import Path

from body.governance.engine_dispatcher import EngineDispatcher
from body.governance.intent_pattern_validators import PatternValidators
from mind.governance.policy_rule import PolicyRule
from mind.governance.violation_report import (
    ConstitutionalViolationError,
    ViolationReport,
)
from shared.config import settings
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
    - Load and prioritize constitutional rules
    - Validate file operations against policies
    - Dispatch to engines for code-level verification
    - Enforce hard invariants (no .intent writes)
    - Support emergency mode with safety guarantees
    """

    _EMERGENCY_LOCK_REL = ".intent/mind/.emergency_override"
    _NO_WRITE_INTENT_RULE = "no_write_intent"

    def __init__(self, repo_path: Path, path_resolver: PathResolver | None = None):
        """
        Initialize IntentGuard with constitutional rules.

        Args:
            repo_path: Absolute path to repository root
            path_resolver: Optional PathResolver (for backward compatibility)
        """
        self.repo_path = Path(repo_path).resolve()

        # Handle path_resolver parameter for backward compatibility
        if path_resolver is not None:
            self.intent_root = path_resolver.intent_root
        else:
            self.intent_root = settings.paths.intent_root

        self.emergency_lock_file = (self.repo_path / self._EMERGENCY_LOCK_REL).resolve()

        # Load governance from IntentRepository
        repo = get_intent_repository()
        repo.initialize()  # CRITICAL: Initialize the repository to build indexes

        # Get precedence map (may return empty dict if no precedence_rules file exists)
        self.precedence_map = repo.get_precedence_map()

        # Parse rules from policies
        raw_rules = repo.list_policy_rules()
        self.rules: list[PolicyRule] = []
        for entry in raw_rules:
            if not isinstance(entry, dict):
                continue
            policy_name = entry.get("policy_name") or "unknown"
            rule_dict = entry.get("rule")
            if isinstance(rule_dict, dict):
                self.rules.append(
                    PolicyRule.from_dict(rule_dict, source=str(policy_name))
                )

        # Apply precedence (lower number = higher priority)
        self.rules.sort(key=lambda r: self.precedence_map.get(r.source_policy, 999))

        logger.info(
            "IntentGuard initialized with %s policy rules for file operation governance.",
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

        Enforcement order:
        1. Hard invariant (.intent writes blocked ALWAYS)
        2. Emergency mode check (bypass policy, never .intent)
        3. Policy rules (precedence-ordered)
        """
        violations: list[ViolationReport] = []

        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()

            # HARD INVARIANT: Absolute block on .intent writes
            if self._is_under_intent(abs_path):
                violations.append(
                    ViolationReport(
                        rule_name=self._NO_WRITE_INTENT_RULE,
                        path=path_str,
                        message="Writes to .intent/ are constitutionally prohibited.",
                        severity="error",
                        suggested_fix="Modify files outside .intent/ only.",
                        source_policy="hard_invariant",
                    )
                )
                continue

            # EMERGENCY BYPASS: Skip policy checks if emergency file exists
            if self._is_emergency_mode():
                logger.warning(
                    "Emergency mode active - bypassing policy checks for: %s", path_str
                )
                continue

            # POLICY EVALUATION: Check constitutional rules
            violations.extend(self._check_against_rules(path_str, abs_path))

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
        violations: list[ViolationReport] = []

        # 1. Path-level validation (hard invariant + rules)
        _allowed, path_violations = self.check_transaction([target_path])
        violations.extend(path_violations)

        # 2. Syntax validation
        try:
            ast.parse(code)
        except SyntaxError as e:
            violations.append(
                ViolationReport(
                    rule_name="valid_python_syntax",
                    path=target_path,
                    message=f"Generated code has syntax error: {e}",
                    severity="error",
                    suggested_fix="Fix syntax before writing to disk.",
                    source_policy="code_quality",
                )
            )

        # 3. Pattern-specific validation (legacy)
        pattern_violations = PatternValidators.validate(
            code, pattern_id, component_type
        )
        violations.extend(pattern_violations)

        # 4. Engine dispatch for deep checks (if configured)
        engine_violations = await EngineDispatcher.validate_code(
            code, target_path, self.rules
        )
        violations.extend(engine_violations)

        return (len(violations) == 0, violations)

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _is_under_intent(self, path: Path) -> bool:
        """Check if path is under .intent/ directory."""
        try:
            path.resolve().relative_to(self.intent_root)
            return True
        except ValueError:
            return False

    def _is_emergency_mode(self) -> bool:
        """Check if emergency override file exists."""
        return self.emergency_lock_file.exists()

    def _check_against_rules(
        self, path_str: str, abs_path: Path
    ) -> list[ViolationReport]:
        """
        Evaluate path against constitutional rules.

        Args:
            path_str: Repo-relative path string
            abs_path: Absolute resolved path

        Returns:
            List of violations
        """
        violations: list[ViolationReport] = []

        for rule in self.rules:
            # Check if rule pattern matches path
            if not rule.matches(path_str):
                continue

            # Evaluate rule action
            if rule.action == "forbid":
                violations.append(
                    ViolationReport(
                        rule_name=rule.name,
                        path=path_str,
                        message=f"Path matches forbidden pattern: {rule.pattern}",
                        severity="error",
                        suggested_fix=rule.rationale or "Avoid this pattern.",
                        source_policy=rule.source_policy,
                    )
                )
            elif rule.action == "review_required":
                violations.append(
                    ViolationReport(
                        rule_name=rule.name,
                        path=path_str,
                        message=f"Path requires human review: {rule.pattern}",
                        severity="warning",
                        suggested_fix=rule.rationale or "Human review required.",
                        source_policy=rule.source_policy,
                    )
                )

        return violations
