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

# Severity value assigned to constitutional-authority violations.
# Using a dedicated string (rather than reusing "error") lets check_transaction
# distinguish "always block" from "block only in strict_mode" without touching
# any shared models.
_CONSTITUTIONAL_SEVERITY = "constitutional"


# ID: 085acfeb-4ce6-4cfb-91eb-544e686a97fb
class IntentGuard:
    """
    Constitutional enforcement orchestrator.

    Responsibilities:
    - Load and prioritize constitutional rules from the Mind.
    - Validate file operations against policies.
    - Enforce hard invariants (no .intent writes).

    Enforcement tiers
    -----------------
    1. Hard invariant (.intent/ writes)
       Unconditional block. No configuration can disable this.

    2. Constitutional rules  (authority="constitution" in the .intent/ file)
       Always block, regardless of strict_mode.
       These are the "sacred" rules that define the system's identity.

    3. Policy rules  (authority="policy")
       Advisory by default (strict_mode=False): violations are reported
       but do NOT block execution, preserving development momentum.
       Set strict_mode=True to make policy violations blocking too.

    Why this split matters
    ----------------------
    Calling strict_mode=False "advisory" is now honest: constitutional rules
    still provide hard enforcement even in the default mode.  The README
    claim "constitutional governance blocks violations" is literally true
    because tier-2 always blocks.  Tier-3 (policy) being advisory during
    development is a deliberate design choice, not a hidden weakness.
    """

    # Sovereign ID from .intent/rules/architecture/governance_basics.json
    _READ_ONLY_RULE_ID = "governance.constitution.read_only"

    def __init__(
        self,
        repo_path: Path,
        path_resolver: PathResolver | None = None,
        strict_mode: bool = False,
    ):
        """
        Initialise IntentGuard.

        Args:
            repo_path: Absolute path to the repository root.
            path_resolver: Optional PathResolver; falls back to repo_path/.intent.
            strict_mode: When True, policy-authority violations (tier-3) also
                         block execution.  Constitutional violations (tier-2)
                         and the .intent/ hard invariant (tier-1) always block
                         regardless of this flag.
        """
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

        # 5. Transform to internal PolicyRule objects (authority is now threaded through)
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
                        authority=er.authority,  # threaded from .intent/ canonical field
                    )
                )

        # 6. Apply precedence
        self.precedence_map = repo.get_precedence_map()
        self.rules.sort(key=lambda r: self.precedence_map.get(r.source_policy, 999))

        constitutional_count = sum(
            1 for r in self.rules if r.authority == "constitution"
        )
        policy_count = len(self.rules) - constitutional_count

        logger.info(
            "IntentGuard initialised: %d constitutional rules (always-block) + "
            "%d policy rules (%s). Strict mode: %s.",
            constitutional_count,
            policy_count,
            "blocking" if strict_mode else "advisory",
            strict_mode,
        )

    # ID: 0955918c-8ada-4631-bd8b-8b186d43203e
    def check_transaction(
        self, proposed_paths: list[str], impact: str | None = None
    ) -> ConstitutionalValidationResult:
        """
        Validate a set of proposed file operations.

        Blocking decision matrix:
        ┌──────────────────────────────┬────────────────────────┐
        │ Violation type               │ Blocks?                │
        ├──────────────────────────────┼────────────────────────┤
        │ .intent/ write (hard inv.)   │ Always                 │
        │ authority="constitution"     │ Always                 │
        │ authority="policy", error    │ Only when strict_mode  │
        │ authority="policy", warning  │ Never                  │
        └──────────────────────────────┴────────────────────────┘
        """
        violations: list[ViolationReport] = []
        has_hard_invariant_violation = False

        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()

            # 1. HARD INVARIANT: Absolute block on .intent writes
            if self._is_under_intent(abs_path):
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
        #
        # Tier 1: .intent/ hard invariant — always blocks (handled above).
        # Tier 2: constitutional authority — always blocks (new).
        # Tier 3: policy authority errors — blocks only in strict_mode.
        #
        # Using _CONSTITUTIONAL_SEVERITY as a sentinel lets us distinguish
        # tiers without modifying ViolationReport or ConstitutionalValidationResult.
        has_constitutional_violations = any(
            v.severity == _CONSTITUTIONAL_SEVERITY for v in violations
        )
        has_policy_errors = any(v.severity == "error" for v in violations)

        is_valid = True
        if has_hard_invariant_violation or has_constitutional_violations:
            is_valid = False
            logger.error(
                "🛑 Constitutional Block: Halting transaction — "
                "hard invariant or constitutional rule violated."
            )
        elif has_policy_errors and self.strict_mode:
            is_valid = False
            logger.error(
                "🛑 Policy Block (strict_mode): Halting transaction — "
                "policy rule violated."
            )
        elif has_policy_errors:
            logger.warning(
                "⚠️  Policy Advisory: violations detected but not blocking "
                "(strict_mode=False). Run with strict_mode=True to enforce."
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

        Severity assigned per rule:
        - authority="constitution" → _CONSTITUTIONAL_SEVERITY  (always-block tier)
        - authority="policy" + is_blocking → "error"           (strict_mode tier)
        - otherwise                        → "warning"          (advisory)
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

            if rule.authority == "constitution":
                # Tier 2: constitutional rule — assign sentinel severity so
                # check_transaction can always-block on it regardless of strict_mode.
                severity = _CONSTITUTIONAL_SEVERITY
            elif is_blocking:
                # Tier 3: policy rule with blocking enforcement — standard error
                # that strict_mode gates on.
                severity = "error"
            else:
                # Advisory only.
                severity = "warning"

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
    """Helper to maintain reference to global engines."""
    return _AUDIT_ENGINES


# =============================================================================
# Global Singleton
# =============================================================================

_INTENT_GUARD: IntentGuard | None = None


# ID: 57841a53-4ecb-4f5f-bbb3-af7e490bd8f9
def get_intent_guard(
    repo_path: Path | None = None,
    path_resolver: PathResolver | None = None,
    strict_mode: bool = False,
) -> IntentGuard:
    """
    Return the global IntentGuard singleton.

    Note on strict_mode
    -------------------
    strict_mode=False (default) does NOT mean "no enforcement".
    Constitutional rules (authority="constitution") always block.
    strict_mode only controls whether *policy* rules (authority="policy")
    are advisory or blocking.  See IntentGuard docstring for the full
    enforcement tier matrix.
    """
    global _INTENT_GUARD
    if _INTENT_GUARD is None:
        if repo_path is None:
            raise ValueError(
                "repo_path is required on first call to get_intent_guard()"
            )
        _INTENT_GUARD = IntentGuard(repo_path, path_resolver, strict_mode)
    return _INTENT_GUARD
