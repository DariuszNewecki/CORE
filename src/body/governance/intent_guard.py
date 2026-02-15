# src/body/governance/intent_guard.py
# ID: 4275c592-2725-4fd1-807f-f0d5d83ea78b

"""
Constitutional Enforcement Engine - Main Orchestrator.

MOVED FROM MIND TO BODY:
IntentGuard performs EXECUTION logic (validation, enforcement decisions).

UPDATED (V2.7.3):
- Strict Mode Toggle: Respects settings.CORE_STRICT_MODE for transaction gating.
- Hard Invariant Protection: .intent/ remains blocked regardless of mode.
"""

from __future__ import annotations

import ast
from pathlib import Path

from body.governance.engine_dispatcher import EngineDispatcher
from body.governance.intent_pattern_validators import PatternValidators
from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.governance.policy_rule import PolicyRule
from mind.governance.rule_extractor import extract_executable_rules
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

# Engine types that perform code-analysis audits (not write-permission gates)
_AUDIT_ENGINES = frozenset({"ast_gate", "knowledge_gate", "llm_gate", "regex_gate"})


# ID: 321feca2-70dd-4301-888f-b2db49795283
class IntentGuard:
    """
    Constitutional enforcement orchestrator.

    Responsibilities:
    - Load and prioritize constitutional rules
    - Validate file operations against policies
    - Enforce hard invariants (no .intent writes)
    - Support switchable strict mode for commercial hardening
    """

    _EMERGENCY_LOCK_REL = ".intent/mind/.emergency_override"
    _NO_WRITE_INTENT_RULE = "no_write_intent"

    def __init__(self, repo_path: Path, path_resolver: PathResolver | None = None):
        """
        Initialize IntentGuard with constitutional rules and enforcement mappings.
        """
        self.repo_path = Path(repo_path).resolve()

        if path_resolver is not None:
            self.intent_root = path_resolver.intent_root
        else:
            self.intent_root = settings.paths.intent_root

        self.emergency_lock_file = (self.repo_path / self._EMERGENCY_LOCK_REL).resolve()

        # 1. Initialize Mind Repository
        repo = get_intent_repository()
        repo.initialize()

        # 2. Initialize Enforcement Mappings
        mapping_loader = EnforcementMappingLoader(self.intent_root)

        # 3. Extract All Policies from Mind
        policies = {}
        for pref in repo.list_policies():
            try:
                policies[pref.policy_id] = repo.load_policy(pref.policy_id)
            except Exception:
                continue

        # 4. Resolve Executable Rules
        executable_rules = extract_executable_rules(policies, mapping_loader)

        # 5. Transform to internal PolicyRule objects
        self.rules: list[PolicyRule] = []
        for er in executable_rules:
            for pattern in er.scope:
                if not pattern or not str(pattern).strip():
                    continue

                self.rules.append(
                    PolicyRule(
                        name=er.rule_id,
                        pattern=str(pattern),
                        action=er.engine or "deny",
                        description=er.statement,
                        severity=er.enforcement,
                        source_policy=er.policy_id,
                        engine=er.engine,
                        params=er.params,
                    )
                )

        # 6. Apply precedence
        self.precedence_map = repo.get_precedence_map()
        self.rules.sort(key=lambda r: self.precedence_map.get(r.source_policy, 999))

        logger.info(
            "IntentGuard initialized with %s enforcement rules.",
            len(self.rules),
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    # ID: 9a9a8177-2d56-4d60-8e99-37d551288e14
    def check_transaction(
        self, proposed_paths: list[str], impact: str | None = None
    ) -> tuple[bool, list[ViolationReport]]:
        """
        Validate a set of proposed file operations.
        """
        violations: list[ViolationReport] = []
        has_hard_invariant_violation = False

        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()

            # HARD INVARIANT: Absolute block on .intent writes (Always blocking)
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
                has_hard_invariant_violation = True
                continue

            # POLICY EVALUATION
            violations.extend(self._check_against_rules(path_str, abs_path, impact))

        # Decision Logic:
        # 1. Hard Invariants ALWAYS block.
        if has_hard_invariant_violation:
            return (False, violations)

        # 2. Check for blocking policy errors
        has_blocking_errors = any(v.severity == "error" for v in violations)

        if has_blocking_errors:
            # THE TEETH TOGGLE:
            if settings.CORE_STRICT_MODE:
                logger.error(
                    "STRICT MODE: Halting transaction due to constitutional violations."
                )
                return (False, violations)
            else:
                logger.warning(
                    "ADVISORY MODE: Permitting transaction despite constitutional violations."
                )
                return (True, violations)

        return (True, violations)

    # ID: 58d875bb-966e-4b82-ab83-66514b9455dc
    async def validate_generated_code(
        self, code: str, pattern_id: str, component_type: str, target_path: str
    ) -> tuple[bool, list[ViolationReport]]:
        """
        Validate generated code against pattern requirements.
        """
        violations: list[ViolationReport] = []

        # 1. Path-level validation
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

        # 4. Engine dispatch for deep checks
        engine_violations = await EngineDispatcher.validate_code(
            code, target_path, self.rules
        )
        violations.extend(engine_violations)

        # For generated code, we are stricter: any violation (even warnings)
        # usually suggests the AI should try again.
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
        self, path_str: str, abs_path: Path, impact: str | None = None
    ) -> list[ViolationReport]:
        """
        Evaluate path against constitutional rules.
        """
        violations: list[ViolationReport] = []
        is_metadata = impact == "write-metadata"

        for rule in self.rules:
            if not rule.pattern:
                continue

            try:
                if not Path(path_str).match(rule.pattern):
                    continue
            except ValueError:
                continue

            if is_metadata and rule.engine in _AUDIT_ENGINES:
                continue

            is_blocking = rule.severity in ("blocking", "error")
            severity = "error" if is_blocking else "warning"

            if is_blocking:
                msg = f"Path matches forbidden pattern: {rule.pattern}"
            else:
                msg = f"Path requires human review: {rule.pattern}"

            violations.append(
                ViolationReport(
                    rule_name=rule.name,
                    path=path_str,
                    message=msg,
                    severity=severity,
                    suggested_fix=rule.description or "Review constitutional policy.",
                    source_policy=rule.source_policy,
                )
            )

        return violations
