# src/mind/governance/checks/safety_rules_check.py
# ID: model.mind.governance.checks.safety_rules_check

"""
Constitutional check for Safety Framework rules.

Uses RuleEnforcementCheck template to verify:
- safety.charter_immutable
- safety.single_active_constitution
- safety.immutable_constitution
- safety.deny_core_loop_edit
- safety.no_dangerous_execution
- safety.change_must_be_logged

Simply declares WHAT to check, not HOW.

SSOT UPDATE:
- This check no longer hard-depends on `.intent/charter/...` paths.
- It resolves the safety standard via AuditorContext's loaded resources (SSOT),
  while keeping legacy references for backward compatibility and messages.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from mind.governance.checks.rule_enforcement_check import RuleEnforcementCheck
from mind.governance.enforcement_methods import (
    AuditLoggingEnforcement,
    CodePatternEnforcement,
    PathProtectionEnforcement,
    SingleInstanceEnforcement,
)


# ID: safety-rules-check
# ID: b114e226-7a80-4f9f-a6b1-67bfb554db26
class SafetyRulesCheck(RuleEnforcementCheck):
    """
    Verifies that all Safety Framework rules are properly enforced.

    SSOT reference:
    - Preferred: AuditorContext.policies provides `standard_operations_safety` (or equivalent).
    - Legacy reference (compat): `.intent/charter/standards/operations/safety.json`
    """

    @property
    def _is_concrete_check(self) -> bool:
        return True

    # Keep a legacy default for compatibility, but RuleEnforcementCheck must be able to
    # resolve policy content via AuditorContext in newer builds.
    policy_file: ClassVar[Path] = Path(
        ".intent/charter/standards/operations/safety.json"
    )

    # NOTE:
    # - expected_patterns here are repo-relative patterns matched by your enforcement methods.
    # - Keep `.intent/charter/**` because it is a behavioral constraint, even if the filesystem
    #   is migrating: IntentGuard/PathResolver can map/alias as needed.
    enforcement_methods: ClassVar[list] = [
        # 1) Charter is immutable - protected paths enforced by IntentGuard
        PathProtectionEnforcement(
            rule_id="safety.charter_immutable",
            expected_patterns=[".intent/charter/**"],
        ),
        # 2) Single active constitution marker
        SingleInstanceEnforcement(
            rule_id="safety.single_active_constitution",
            target_file="charter/constitution/ACTIVE",
        ),
        # 3) Core mission files immutable
        PathProtectionEnforcement(
            rule_id="safety.immutable_constitution",
            expected_patterns=[
                "mind/knowledge/domain_definitions.yaml",
                "mind_export/northstar.yaml",
            ],
        ),
        # 4) Core loop cannot be edited without review
        PathProtectionEnforcement(
            rule_id="safety.deny_core_loop_edit",
            expected_patterns=[
                "src/core/main.py",
                "src/core/intent_guard.py",
                ".intent/charter/policies/safety_framework.json",
            ],
        ),
        # 5) No dangerous code execution patterns
        CodePatternEnforcement(
            rule_id="safety.no_dangerous_execution",
            required_patterns=[
                r"eval\(",
                r"exec\(",
                r"subprocess\.(run|Popen|call)\([^)]*shell\s*=\s*True",
            ],
        ),
        # 6) All changes must be logged with intent
        AuditLoggingEnforcement(
            rule_id="safety.change_must_be_logged",
            required_fields=["intent_bundle_id"],
        ),
    ]
