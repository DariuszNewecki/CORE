# src/mind/governance/intent_guard.py
"""
Constitutional Enforcement Engine - Main Orchestrator.

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

from mind.governance.engine_dispatcher import EngineDispatcher
from mind.governance.intent_pattern_validators import PatternValidators
from mind.governance.policy_rule import PolicyRule
from mind.governance.violation_report import (
    ConstitutionalViolationError,
    ViolationReport,
)
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

    def __init__(self, repo_path: Path, path_resolver: PathResolver):
        """
        Initialize IntentGuard with constitutional rules.

        Args:
            repo_path: Absolute path to repository root
            path_resolver: PathResolver for intent_root and path resolution
        """
        self.repo_path = Path(repo_path).resolve()
        self._path_resolver = path_resolver
        self.intent_root = self._path_resolver.intent_root
        self.emergency_lock_file = (self.repo_path / self._EMERGENCY_LOCK_REL).resolve()

        # Load governance from IntentRepository
        repo = get_intent_repository()
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
        3. Policy rules (pattern matching + engine dispatch)
        """
        violations: list[ViolationReport] = []

        # Hard invariant: no .intent writes EVER
        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()
            hard = self._check_no_write_intent(abs_path, path_str)
            if hard is not None:
                violations.append(hard)

        if violations:
            return (False, violations)

        # Emergency mode bypass (non-.intent paths only)
        if self._is_emergency_mode():
            logger.critical(
                "INTENT GUARD BYPASSED (EMERGENCY MODE) for non-.intent paths: %s",
                proposed_paths,
            )
            return (True, [])

        # Policy enforcement with engine dispatch
        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()
            violations.extend(self._check_single_path(abs_path, path_str))

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

        # Hard invariant
        abs_target = (self.repo_path / target_path).resolve()
        hard = self._check_no_write_intent(abs_target, target_path)
        if hard is not None:
            return (False, [hard])

        # Emergency bypass
        if self._is_emergency_mode():
            logger.critical(
                "CODE VALIDATION BYPASSED (EMERGENCY MODE): %s", target_path
            )
            return (True, [])

        violations: list[ViolationReport] = []

        # FIX FOR STEP 10: Handle V2 Utility patterns.
        # These are pure logic and only require valid syntax.
        if pattern_id in ("pure_function", "stateless_utility"):
            try:
                ast.parse(code)
                # If syntax is valid, it passes.
            except SyntaxError as e:
                violations.append(
                    ViolationReport(
                        rule_name="syntax_error",
                        path=target_path,
                        message=f"Syntax error in generated utility: {e}",
                        severity="error",
                        source_policy="code_purity",
                    )
                )
                return (False, violations)

        # Legacy pattern validators (for Commands and Actions)
        if pattern_id == "inspect_pattern":
            violations.extend(
                PatternValidators.validate_inspect_pattern(code, target_path)
            )
        elif pattern_id == "action_pattern":
            violations.extend(
                PatternValidators.validate_action_pattern(code, target_path)
            )
        elif pattern_id == "check_pattern":
            violations.extend(
                PatternValidators.validate_check_pattern(code, target_path)
            )
        elif pattern_id == "run_pattern":
            violations.extend(PatternValidators.validate_run_pattern(code, target_path))

        # Path-level enforcement (IDs, Headers, etc.)
        violations.extend(self._check_single_path(abs_target, target_path))

        return (len(violations) == 0, violations)

    # -------------------------------------------------------------------------
    # Internal enforcement logic
    # -------------------------------------------------------------------------

    def _is_emergency_mode(self) -> bool:
        """Check if emergency override is active."""
        return self.emergency_lock_file.exists()

    def _check_single_path(self, path: Path, path_str: str) -> list[ViolationReport]:
        """
        Enforce constitutional rules against a single path.

        Applies all matching rules with engine dispatch where specified.
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

    def _check_no_write_intent(
        self, abs_path: Path, rel_path_str: str
    ) -> ViolationReport | None:
        """
        HARD INVARIANT: .intent/** is never writable by CORE.

        This rule has no bypass, no emergency override, no exceptions.
        """
        try:
            intent_root = Path(self.intent_root).resolve()
            if abs_path == intent_root or intent_root in abs_path.parents:
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

    def _check_policy_rules(self, path: Path, path_str: str) -> list[ViolationReport]:
        """
        Apply all matching constitutional rules to a path.

        Rules are applied in precedence order. Engine-based rules are
        dispatched to EngineDispatcher for verification.
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

    def _apply_rule_action(
        self, rule: PolicyRule, path: Path, path_str: str
    ) -> list[ViolationReport]:
        """
        Execute rule enforcement.

        Dispatches to engine if rule specifies one, otherwise applies
        simple deny/warn action.
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

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Glob-based pattern matching."""
        if not pattern:
            return False
        return Path(path).match(pattern)
