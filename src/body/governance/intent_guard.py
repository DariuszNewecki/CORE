# src/body/governance/intent_guard.py

"""
Constitutional Intent Guard - Main Orchestrator.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

from body.governance.intent_pattern_validators import PatternValidators
from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.governance.policy_rule import PolicyRule
from mind.governance.rule_extractor import extract_executable_rules
from mind.governance.violation_report import ViolationReport
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.intent.operational_capabilities import (
    OperationalCapability,
    OperationalCapabilityTaxonomyError,
    load_operational_capabilities,
)
from shared.infrastructure.intent.vocabulary_projection import (
    VocabularyProjectionError,
    load_vocabulary_projection,
)
from shared.logger import getLogger
from shared.models.constitutional_validation import ConstitutionalValidationResult
from shared.path_resolver import PathResolver
from shared.utils.glob_match import matches_glob


logger = getLogger(__name__)

# Engine types that MUST NOT be evaluated by check_transaction at write time.
#
# Two distinct categories share this property:
#
# 1. Content-analysis engines (need file content, only available at audit phase):
#       ast_gate, glob_gate, knowledge_gate, llm_gate, regex_gate
#
# 2. Passive-marker engines (no write-time check exists; enforcement happens
#    elsewhere — at runtime, at parse time, at decoration, or by code review):
#       runtime_check        → enforced by cli_gate at audit/self-check time
#       python_runtime       → enforced by Python at module import
#       dataclass_validation → enforced by Pydantic __post_init__
#       type_system          → enforced by Python enum type-checking
#       advisory             → enforced by code review (by design)
#       runtime_metric       → tracked, not enforced
#
# Evaluating either category here produces false positives: the rule has no
# applicable check, and check_transaction would emit the rule's statement as
# a block reason. See issue #142 — fix.placeholders failures (128/129 of all
# autonomous failures, 2026-04-22 → 2026-04-23) traced to runtime_check rules
# being treated as write-time gates.
_AUDIT_ENGINES = frozenset(
    {
        "ast_gate",
        "glob_gate",
        "knowledge_gate",
        "llm_gate",
        "regex_gate",
        "runtime_check",
        "python_runtime",
        "dataclass_validation",
        "type_system",
        "advisory",
        "runtime_metric",
        "taxonomy_gate",
    }
)

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

        # ADR-079 D2/D5: capability taxonomy index for chokepoint authorization.
        # Stage 1 is advisory — a load failure logs and disables the tier rather
        # than failing startup. Stage 4+ promotion will tighten this to fail-closed.
        self._capabilities: Mapping[str, OperationalCapability] | None
        try:
            caps = load_operational_capabilities(self.repo_path)
            self._capabilities = {c.id: c for c in caps}
            logger.info(
                "Capability taxonomy loaded: %d entries (chokepoint tier: advisory).",
                len(self._capabilities),
            )
        except OperationalCapabilityTaxonomyError as exc:
            self._capabilities = None
            logger.warning(
                "Capability taxonomy not loaded; chokepoint tier will no-op. Reason: %s",
                exc,
            )

    # ID: 0955918c-8ada-4631-bd8b-8b186d43203e
    def check_transaction(
        self,
        proposed_paths: list[str],
        impact: str | None = None,
        op_classes: Mapping[str, str] | None = None,
        calling_capability: str | None = None,
        current_mode: str | None = None,
        target_classes: Mapping[str, str] | None = None,
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
        │ capability tier (ADR-079)    │ Never — advisory only  │
        └──────────────────────────────┴────────────────────────┘

        DEGRADED pre-check (ADR-023 D4): if the vocabulary projection is
        BROKEN, governance evaluation cannot run — block all writes and
        return a single instrument-degraded violation. This preserves the
        invariant that governance evaluation is only possible when the
        governance instrument is healthy.

        ADR-079 stage 1 (advisory): the capability tier evaluates D5
        branches 3-8 and emits ``chokepoint.advisory.would-deny`` log
        lines for paths that would be denied. The tier does NOT affect
        ``is_valid`` or the returned ``violations`` list in this stage —
        log-only observability. Stage 3+ promotes the tier to blocking
        per-capability per the D10 migration sequence.

        ADR-097 step 2 (additive): ``target_classes`` is an optional
        per-path map (``path -> target_class``) that selects the D3
        behavior tier. When omitted, every path falls through to the
        existing repo-source behavior (hard invariant + policy rules) —
        byte-identical to pre-ADR-097 callers. When supplied:

        - ``repo-source`` / ``runtime-output`` / ``governed-artifact``
          → existing behavior (hard invariant + policy rules). The
          governed-artifact API-mediated tier is reserved for step 6;
          today these paths hit the .intent/ hard invariant and the
          ordinary policy rules just like repo-source paths.
        - ``ephemeral-scratch`` → policy/invariant evaluation is
          skipped. Capability tier still runs (ADR-079 stage 1, log
          only). This is the structural sanctuary that lets
          shadow_materializer / sandbox writes pass the chokepoint
          without per-file excludes.
        """
        projection = load_vocabulary_projection(self.repo_path)
        if isinstance(projection, VocabularyProjectionError):
            logger.error(
                "🛑 Governance DEGRADED: vocabulary projection broken — %s",
                projection.reason,
            )
            return ConstitutionalValidationResult(
                is_valid=False,
                violations=[
                    ViolationReport(
                        rule_name="governance.instrument_degraded",
                        path=", ".join(proposed_paths) if proposed_paths else "<n/a>",
                        message=(
                            "Governance vocabulary projection is broken; "
                            f"writes are blocked until restored. Reason: {projection.reason}. "
                            "Run `core-admin intent sync vocabulary --write` to repair."
                        ),
                        severity="error",
                        suggested_fix="Repair .intent/META/vocabulary.json via the regen command.",
                        source_policy="constitution",
                    )
                ],
                source="IntentGuard",
            )

        violations: list[ViolationReport] = []
        has_hard_invariant_violation = False

        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()

            # ADR-079 stage 1 (advisory). Capability tier runs alongside the
            # existing tiers and emits log-only "would-deny" observations.
            # Does not contribute to violations or is_valid in stage 1.
            self._evaluate_capability_tier_advisory(
                path_str=path_str,
                op_class=(op_classes or {}).get(path_str),
                capability=calling_capability,
                mode=current_mode,
            )

            # ADR-097 step 2: target-class dispatch.
            # ephemeral-scratch skips the rest of per-path evaluation:
            # the path is by-construction non-committal (under var/tmp/),
            # so no hard invariant or policy rule should fire on it. The
            # capability tier already ran above. When target_classes is
            # not supplied, this resolves to None and the existing
            # repo-source-equivalent flow runs (backwards-compatible).
            target_class = self._resolve_target_class_for_path(path_str, target_classes)
            if target_class == "ephemeral-scratch":
                continue

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

        # 3. Pattern-specific validation (candidates for Strike 1 Phase 3).
        # PatternValidators.validate dispatches by pattern_id and returns an
        # empty list when no validator applies (issue #210). target_path is
        # forwarded so dispatched per-pattern validators receive the path
        # they expect.
        pattern_violations = PatternValidators.validate(
            code, pattern_id, component_type, target_path
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

    def _resolve_target_class_for_path(
        self,
        path_str: str,
        target_classes: Mapping[str, str] | None,
    ) -> str | None:
        """Return the ADR-097 D2 target_class for a path, or None to defer to default behavior.

        When the caller passes ``target_classes``, the supplied value
        wins. When omitted (every pre-ADR-097 caller), this returns
        None and the per-path loop falls through to the existing
        repo-source-equivalent flow. ADR-097 step 4 makes FileHandler
        the first caller that supplies the map.
        """
        if target_classes is not None and path_str in target_classes:
            return target_classes[path_str]
        return None

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

        for rule in self.rules:
            if not rule.pattern:
                continue

            if not matches_glob(path_str, rule.pattern):
                continue

            # Skip engines that have no write-time check — either content-analysis
            # engines (need file content) or passive-marker engines (enforced at
            # runtime, parse time, decoration, or by code review). See _AUDIT_ENGINES.
            if rule.engine in _audit_engines_set():
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

    def _evaluate_capability_tier_advisory(
        self,
        *,
        path_str: str,
        op_class: str | None,
        capability: str | None,
        mode: str | None,
    ) -> None:
        """Stage 1 capability-tier evaluation: emit advisory log lines only.

        Implements ADR-079 D5 branches 3-8. Does NOT mutate violations or
        is_valid. Logs at INFO with marker ``chokepoint.advisory.would-deny``
        when a path would be denied; logs at DEBUG with marker
        ``chokepoint.advisory.would-permit`` on a permit.

        No-ops if any input required to make a decision is absent — the
        chokepoint reads context up-stack and stage-1 callers (FileHandler)
        always supply all four; other callers (e.g. validate_generated_code's
        target_path probe) pass none and the tier is skipped.
        """
        if self._capabilities is None or op_class is None or mode is None:
            return

        # Branch 3: no capability in context (paper §7).
        if capability is None:
            logger.info(
                "chokepoint.advisory.would-deny op_class=%s path=%s mode=%s "
                "capability=<none> reason=no_capability_context",
                op_class,
                path_str,
                mode,
            )
            return

        # Branch 4: unknown capability.
        cap = self._capabilities.get(capability)
        if cap is None:
            logger.info(
                "chokepoint.advisory.would-deny op_class=%s path=%s mode=%s "
                "capability=%s reason=unknown_capability",
                op_class,
                path_str,
                mode,
                capability,
            )
            return

        fs_profile = cap.as_mapping
        entries = fs_profile.get(op_class, ())

        # Branch 5: op-class not declared (empty list for this op_class).
        if not entries:
            logger.info(
                "chokepoint.advisory.would-deny op_class=%s path=%s mode=%s "
                "capability=%s reason=operation_not_authorized",
                op_class,
                path_str,
                mode,
                capability,
            )
            return

        # Branch 6: no matching path pattern.
        matching = [e for e in entries if matches_glob(path_str, e.path_pattern)]
        if not matching:
            declared = [e.path_pattern for e in entries]
            logger.info(
                "chokepoint.advisory.would-deny op_class=%s path=%s mode=%s "
                "capability=%s reason=path_not_authorized declared_patterns=%s",
                op_class,
                path_str,
                mode,
                capability,
                declared,
            )
            return

        # Branch 7: mode-excluded.
        if not any(mode in e.modes for e in matching):
            logger.info(
                "chokepoint.advisory.would-deny op_class=%s path=%s mode=%s "
                "capability=%s reason=mode_not_authorized",
                op_class,
                path_str,
                mode,
                capability,
            )
            return

        # Branch 8: permit.
        logger.debug(
            "chokepoint.advisory.would-permit op_class=%s path=%s mode=%s capability=%s",
            op_class,
            path_str,
            mode,
            capability,
        )


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
