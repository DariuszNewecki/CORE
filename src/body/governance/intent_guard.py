# src/body/governance/intent_guard.py
# ID: 4275c592-2725-4fd1-807f-f0d5d83ea78b

"""
Constitutional Intent Guard - Main Orchestrator.
"""

from __future__ import annotations

import ast
from pathlib import Path

from body.governance.intent_pattern_validators import PatternValidators
from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.governance.policy_rule import PolicyRule
from mind.governance.rule_extractor import extract_executable_rules
from mind.governance.violation_report import ViolationReport
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger
from shared.models.constitutional_validation import ConstitutionalValidationResult
from shared.path_resolver import PathResolver


logger = getLogger(__name__)

# Engine types that perform code-analysis audits (not write-permission gates)
_AUDIT_ENGINES = frozenset({"ast_gate", "knowledge_gate", "llm_gate", "regex_gate"})


# ID: 085acfeb-4ce6-4cfb-91eb-544e686a97fb
class IntentGuard:
    """
    Constitutional enforcement orchestrator.

    Responsibilities:
    - Load and prioritize constitutional rules from the Mind.
    - Validate file operations against policies.
    - Enforce hard invariants (no .intent writes).
    """

    # Sovereign ID from .intent/rules/architecture/governance_basics.json
    _READ_ONLY_RULE_ID = "governance.constitution.read_only"

    def __init__(
        self,
        repo_path: Path,
        path_resolver: PathResolver | None = None,
        strict_mode: bool = False,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.strict_mode = strict_mode

        if path_resolver is not None:
            self.intent_root = path_resolver.intent_root
        else:
            self.intent_root = self.repo_path / ".intent"

        # 1. Initialize Mind Repository
        repo = get_intent_repository()
        repo.initialize()

        # 2. Initialize Enforcement Mappings
        mapping_loader = EnforcementMappingLoader(self.intent_root)

        # 3. Extract All Policies from Mind
        policies = {
            pref.policy_id: repo.load_policy(pref.policy_id)
            for pref in repo.list_policies()
        }

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
            "IntentGuard initialized with %s enforcement rules (Strict: %s).",
            len(self.rules),
            self.strict_mode,
        )

    # ID: 0955918c-8ada-4631-bd8b-8b186d43203e
    def check_transaction(
        self, proposed_paths: list[str], impact: str | None = None
    ) -> ConstitutionalValidationResult:
        """
        Validate a set of proposed file operations.
        """
        violations: list[ViolationReport] = []
        has_hard_invariant_violation = False

        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()

            # 1. HARD INVARIANT: Absolute block on .intent writes
            if self._is_under_intent(abs_path):
                # Sensation: Look up the sovereign rule to get the correct metadata
                rule = next(
                    (r for r in self.rules if r.name == self._READ_ONLY_RULE_ID), None
                )

                violations.append(
                    ViolationReport(
                        rule_name=self._READ_ONLY_RULE_ID,
                        path=path_str,
                        message=(
                            rule.description
                            if rule
                            else "Writes to .intent/ are constitutionally prohibited."
                        ),
                        severity="error",
                        suggested_fix="Modify files outside .intent/ only.",
                        source_policy="constitution",
                    )
                )
                has_hard_invariant_violation = True
                continue

            # 2. POLICY EVALUATION
            violations.extend(self._check_against_rules(path_str, abs_path, impact))

        # 3. DECISION LOGIC (The Teeth)
        # Hard Invariants ALWAYS block. Policy errors block only in strict_mode.
        has_blocking_errors = any(v.severity == "error" for v in violations)

        is_valid = True
        if has_hard_invariant_violation or (has_blocking_errors and self.strict_mode):
            is_valid = False
            logger.error(
                "🛑 Constitutional Block: Halting transaction due to violations."
            )

        return ConstitutionalValidationResult(
            is_valid=is_valid, violations=violations, source="IntentGuard"
        )

    # ID: a4679305-9d00-4a14-af38-32a729a33a20
    def validate_generated_code(
        self, code: str, pattern_id: str, component_type: str, target_path: str
    ) -> ConstitutionalValidationResult:
        """
        Validate generated code against pattern requirements.
        """
        # Start with a clean result
        result = ConstitutionalValidationResult(is_valid=True, source="IntentGuard")

        # 1. Path-level validation
        path_res = self.check_transaction([target_path])
        result.merge(path_res)

        # 2. Syntax validation
        try:
            ast.parse(code)
        except SyntaxError as e:
            result.add_violation(
                ViolationReport(
                    rule_name="valid_python_syntax",
                    path=target_path,
                    message=f"Generated code has syntax error: {e}",
                    severity="error",
                    suggested_fix="Fix syntax before writing to disk.",
                    source_policy="code_quality",
                )
            )

        # 3. Pattern-specific validation (legacy shim - candidates for Strike 1 Phase 3)
        pattern_violations = PatternValidators.validate(
            code, pattern_id, component_type
        )
        for v in pattern_violations:
            result.add_violation(v)

        return result

    def _is_under_intent(self, path: Path) -> bool:
        """Check if path is under .intent/ directory."""
        try:
            path.resolve().relative_to(self.intent_root)
            return True
        except ValueError:
            return False

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

            # Skip audit-only engines if this is just a metadata tag
            if is_metadata and rule.engine in _audit_engines_set():
                continue

            is_blocking = rule.severity in ("blocking", "error")
            severity = "error" if is_blocking else "warning"

            violations.append(
                ViolationReport(
                    rule_name=rule.name,
                    path=path_str,
                    message=rule.description
                    or f"Path matches restricted pattern: {rule.pattern}",
                    severity=severity,
                    source_policy=rule.source_policy,
                )
            )

        return violations


def _audit_engines_set():
    """Helper to maintain reference to globalengines."""
    return _AUDIT_ENGINES


# =============================================================================
# Global Singleton
# =============================================================================

_INTENT_GUARD: IntentGuard | None = None


# ID: 0f6335c2-bea4-4ac6-b5d5-072591871d66
def get_intent_guard(
    repo_path: Path | None = None,
    path_resolver: PathResolver | None = None,
    strict_mode: bool = False,
) -> IntentGuard:
    """Return the global IntentGuard singleton."""
    global _INTENT_GUARD
    if _INTENT_GUARD is None:
        if repo_path is None:
            raise ValueError(
                "repo_path is required on first call to get_intent_guard()"
            )
        _INTENT_GUARD = IntentGuard(repo_path, path_resolver, strict_mode)
    return _INTENT_GUARD
