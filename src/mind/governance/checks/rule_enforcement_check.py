# src/mind/governance/checks/rule_enforcement_check.py

"""
Abstract template for constitutional rule enforcement checks.

Provides a standardized pattern for verifying that constitutional rules
are actually enforced in the codebase, not just declared in policy files.

Option A (SSOT): Uses AuditorContext.policies as the canonical source.

Constitutional rule:
- This template MUST NOT load policy files from disk.
- Policy resolution MUST go through AuditorContext's loaded resources.

Rationale:
- Prevents path-churn during .intent layout changes
- Eliminates duplicate “load JSON/YAML” logic across checks
- Ensures all checks observe the same SSOT snapshot the Auditor produced
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 7f9cea7d-99dc-4112-a586-7e085a8e5991
class EnforcementMethod(ABC):
    """
    Base class for enforcement verification strategies.
    Each method answers: "Is this rule actually enforced?"
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        self.rule_id = rule_id
        self.severity = severity

    @abstractmethod
    # ID: 2f4c79cf-8880-4c39-9b06-bdcae96c322b
    def verify(
        self,
        context: AuditorContext,
        rule_data: dict[str, Any],
        **kwargs,
    ) -> list[AuditFinding]:
        """
        Verify that enforcement exists for this rule.

        **kwargs is intentionally supported to allow checks to pass runtime parameters
        (e.g., threshold, scope, file filters) without breaking the template contract.
        """
        raise NotImplementedError

    def _create_finding(
        self,
        message: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> AuditFinding:
        """Helper to create standardized findings."""
        return AuditFinding(
            check_id=self.rule_id,
            severity=self.severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
        )


# ID: 359472f9-642e-4bff-b93b-4cd1e18e81f7
class RuleEnforcementCheck(BaseCheck, ABC):
    """
    Abstract template for verifying that constitutional rules are enforced.

    Subclasses declare:
    - policy_file: Path-like hint used ONLY to derive SSOT lookup keys.
                  Do NOT assume it exists on disk.
    - enforcement_methods: List of verification strategies

    SSOT (required): policies are resolved via AuditorContext.policies.
    """

    policy_file: ClassVar[Path | None] = None
    enforcement_methods: ClassVar[list[EnforcementMethod]] = []

    @property
    @abstractmethod
    def _is_concrete_check(self) -> bool:
        """Subclasses must override this to return True."""
        raise NotImplementedError

    def __init__(self, context: AuditorContext):
        super().__init__(context)

        if self.__class__ is RuleEnforcementCheck:
            raise TypeError("RuleEnforcementCheck is abstract.")

        if self.__class__.policy_file is None:
            raise ValueError(f"{self.__class__.__name__} must set policy_file")

        if not self.__class__.enforcement_methods:
            raise ValueError(f"{self.__class__.__name__} must set enforcement_methods")

        # Auto-populate policy_rule_ids for coverage tracking.
        # Note: BaseCheck __init__ runs before this and may warn; that's acceptable.
        if not self.policy_rule_ids:
            self.policy_rule_ids = [
                method.rule_id for method in self.__class__.enforcement_methods
            ]

    # ID: a19b69aa-b618-4f69-af0e-014bc8cefde0
    def execute(self, **kwargs) -> list[AuditFinding]:
        """
        Template method: orchestrates SSOT-based verification.

        Contract:
        - Never reads policy files from disk
        - Uses the AuditorContext snapshot only
        - Accepts **kwargs for runtime parametrization (e.g., threshold)
        """
        findings: list[AuditFinding] = []

        policy_data = self._resolve_policy_from_ssot()
        if policy_data is None:
            available: list[str] = []
            paths = getattr(self.context, "paths", None)
            if paths is not None and hasattr(paths, "list_policies"):
                try:
                    available = list(paths.list_policies())
                except Exception:
                    available = []

            findings.append(
                AuditFinding(
                    check_id="policy.file.missing",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "Policy missing in SSOT (AuditorContext.policies). "
                        f"Hint: {self.__class__.policy_file}. "
                        "This check is SSOT-only; filesystem fallbacks are forbidden."
                    ),
                    file_path="SSOT:policies",
                    context={
                        "lookup_hints": self._policy_lookup_hints(),
                        "available_policy_keys": available[:40],
                        "available_policy_key_count": len(available),
                    },
                )
            )
            return findings

        rules = policy_data.get("rules", [])
        if not isinstance(rules, list):
            findings.append(
                AuditFinding(
                    check_id="rules.missing",
                    severity=AuditSeverity.ERROR,
                    message="Policy declares no enforceable rules (expected flat 'rules' list).",
                    file_path=self._policy_identity_for_evidence(policy_data),
                )
            )
            return findings

        rules_by_id: dict[str, dict[str, Any]] = {
            str(rule.get("id")): rule
            for rule in rules
            if isinstance(rule, dict) and isinstance(rule.get("id"), str)
        }

        for method in self.__class__.enforcement_methods:
            rule_data = rules_by_id.get(method.rule_id)
            if rule_data is None:
                findings.append(
                    AuditFinding(
                        check_id=method.rule_id,
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Rule '{method.rule_id}' not declared in policy "
                            f"(lookup hints: {self._policy_lookup_hints()})"
                        ),
                        file_path=self._policy_identity_for_evidence(policy_data),
                    )
                )
                continue

            try:
                findings.extend(method.verify(self.context, rule_data, **kwargs))
            except Exception as exc:
                logger.error(
                    "Enforcement failed for %s: %s", method.rule_id, exc, exc_info=True
                )
                findings.append(
                    AuditFinding(
                        check_id=method.rule_id,
                        severity=AuditSeverity.ERROR,
                        message=f"Enforcement method raised exception: {exc}",
                        file_path=self._policy_identity_for_evidence(policy_data),
                    )
                )

        return findings

    def _policy_lookup_hints(self) -> list[str]:
        """
        Convert a legacy Path hint into likely SSOT keys.

        AuditorContext indexes resources under multiple keys, including:
        - namespaced keys: 'policies/<key>', 'standards/<key>', 'constitution/<key>'
        - raw canonical keys: '<key>'
        - file stem: '<stem>'
        - internal ids: 'id', 'policy_id'
        """
        hint = str(self.__class__.policy_file or "")
        hint = hint.replace("\\", "/").strip()

        # Strip extension
        if "." in hint:
            hint = hint.rsplit(".", 1)[0]

        # Strip leading intent roots (canonical + legacy)
        prefixes = (
            ".intent/policies/",
            ".intent/standards/",
            ".intent/constitution/",
            ".intent/charter/standards/",
            ".intent/charter/constitution/",
            ".intent/charter/policies/",
            ".intent/charter/",
            ".intent/",
        )
        for prefix in prefixes:
            if hint.startswith(prefix):
                hint = hint[len(prefix) :]
                break

        hint = hint.lstrip("/")

        stem = Path(hint).name if hint else ""

        # Ordered by likelihood given your AuditorContext indexing strategy
        candidates = [
            f"policies/{hint}" if hint else "",
            hint,
            stem,
            f"standards/{hint}" if hint else "",
            f"constitution/{hint}" if hint else "",
        ]
        return [c for c in candidates if c]

    def _policy_identity_for_evidence(self, policy: dict[str, Any]) -> str:
        pid = policy.get("id") or policy.get("policy_id") or "unknown_policy"
        return f"SSOT:{pid}"

    def _resolve_policy_from_ssot(self) -> dict[str, Any] | None:
        """
        Resolve policy from AuditorContext.policies (SSOT only).
        """
        policies = getattr(self.context, "policies", None)
        if not isinstance(policies, dict):
            logger.warning("AuditorContext.policies is missing or invalid.")
            return None

        # 1) Direct key hits via derived hints
        for key in self._policy_lookup_hints():
            candidate = policies.get(key)
            if isinstance(candidate, dict):
                return candidate

        # 2) Fallback: scan for a matching id/policy_id that aligns with the hint stem
        hint_stem = Path(str(self.__class__.policy_file or "")).stem.lower()
        if hint_stem:
            for _k, candidate in policies.items():
                if not isinstance(candidate, dict):
                    continue
                pid = str(
                    candidate.get("id") or candidate.get("policy_id") or ""
                ).lower()
                if pid and (pid.endswith(hint_stem) or hint_stem in pid):
                    return candidate

        return None
