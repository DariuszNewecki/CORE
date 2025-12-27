# src/mind/governance/checks/rule_enforcement_check.py

"""
Abstract template for constitutional rule enforcement checks.

Provides a standardized pattern for verifying that constitutional rules
are actually enforced in the codebase, not just declared in policy files.

SSOT rule:
- This template MUST NOT load policy files from disk.
- Policy resolution MUST go through AuditorContext's loaded resources.

Migration note (Option B):
- Checks MAY omit policy_file and bind directly via policy_rule_ids.
  This supports incremental migration away from path-based policy resolution.
"""

from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable
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
        **kwargs: Any,
    ) -> list[AuditFinding] | Any:
        """
        Verify that enforcement exists for this rule.

        Implementations MAY be async (return awaitable).
        The template will normalize outputs to list[AuditFinding].
        """
        raise NotImplementedError

    def _create_finding(
        self,
        message: str,
        file_path: str | None = None,
        line_number: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditFinding:
        return AuditFinding(
            check_id=self.rule_id,
            severity=self.severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
            details=details or {},
        )


# ID: 359472f9-642e-4bff-b93b-4cd1e18e81f7
class RuleEnforcementCheck(BaseCheck, ABC):
    """
    Abstract template for verifying that constitutional rules are enforced.

    Subclasses declare either:
    - policy_file: Path-like hint used ONLY to derive SSOT lookup keys
      (do NOT assume it exists on disk), OR
    - policy_rule_ids: explicit rule IDs this check enforces (migration-friendly).

    SSOT: policies are resolved via AuditorContext.policies.
    """

    # Optional hint for legacy/migration lookup; must never be read from disk here.
    policy_file: ClassVar[Path | None] = None

    # Preferred declaration (Option B): explicit rule IDs this check binds to.
    # Subclasses may set this; otherwise we derive from enforcement_methods.
    policy_rule_ids: ClassVar[tuple[str, ...]] = ()

    # Prefer tuple to avoid accidental class-level mutation.
    enforcement_methods: ClassVar[tuple[EnforcementMethod, ...]] = ()

    @property
    @abstractmethod
    def _is_concrete_check(self) -> bool:
        raise NotImplementedError

    def __init__(self, context: AuditorContext):
        super().__init__(context)

        if self.__class__ is RuleEnforcementCheck:
            raise TypeError("RuleEnforcementCheck is abstract.")

        if not self.__class__.enforcement_methods:
            raise ValueError(f"{self.__class__.__name__} must set enforcement_methods")

        has_policy_file = self.__class__.policy_file is not None
        has_rule_ids = bool(self.__class__.policy_rule_ids)

        if not has_policy_file and not has_rule_ids:
            raise ValueError(
                f"{self.__class__.__name__} must set policy_file OR policy_rule_ids"
            )

        # Instance-level list for reporting/debug, derived safely.
        self._bound_rule_ids: list[str] = self._derive_bound_rule_ids()

    def _derive_bound_rule_ids(self) -> list[str]:
        if self.__class__.policy_rule_ids:
            return list(self.__class__.policy_rule_ids)
        return [m.rule_id for m in self.__class__.enforcement_methods]

    @staticmethod
    def _run_maybe_awaitable(value: Any) -> Any:
        if not inspect.isawaitable(value):
            return value

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(value)

        raise RuntimeError(
            "RuleEnforcementCheck.execute encountered an awaitable while an event loop "
            "is running. Caller must await instead of calling synchronously."
        )

    # ID: a19b69aa-b618-4f69-af0e-014bc8cefde0
    def execute(self, **kwargs: Any) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        policy_data = self._resolve_policy_from_ssot()
        if policy_data is None:
            findings.append(
                AuditFinding(
                    check_id="policy.missing",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "Policy missing in SSOT (AuditorContext.policies). "
                        "This check is SSOT-only; filesystem fallbacks are forbidden."
                    ),
                    file_path="SSOT:policies",
                    details={
                        "lookup_hints": self._policy_lookup_hints(),
                        "policy_rule_ids": list(self._bound_rule_ids),
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
                    message=(
                        "Policy declares no enforceable rules "
                        "(expected flat 'rules' list)."
                    ),
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
                        message=f"Rule '{method.rule_id}' not declared in policy.",
                        file_path=self._policy_identity_for_evidence(policy_data),
                        details={"lookup_hints": self._policy_lookup_hints()},
                    )
                )
                continue

            try:
                out = method.verify(self.context, rule_data, **kwargs)
                out = self._run_maybe_awaitable(out)

                if out is None:
                    continue
                if not isinstance(out, list):
                    raise TypeError(
                        "EnforcementMethod.verify must return list[AuditFinding], "
                        f"got {type(out)}"
                    )

                findings.extend(out)

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
        Return SSOT lookup hints for AuditorContext.policies.

        If policy_file is absent (Option B), we return rule-id based hints so the
        missing-policy finding remains actionable.
        """
        policy_file = self.__class__.policy_file
        if policy_file is None:
            weak = [f"rules/{rid}" for rid in self._bound_rule_ids[:5]]
            return [*weak, "policy_file:none"]

        hint = str(policy_file).replace("\\", "/").strip()
        if "." in hint:
            hint = hint.rsplit(".", 1)[0]

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

        candidates = [
            f"policies/{hint}" if hint else "",
            hint,
            stem,
            f"standards/{hint}" if hint else "",
            f"constitution/{hint}" if hint else "",
        ]
        return [c for c in candidates if c]

    @staticmethod
    def _policy_identity_for_evidence(policy: dict[str, Any]) -> str:
        pid = policy.get("id") or policy.get("policy_id") or "unknown_policy"
        return f"SSOT:{pid}"

    def _resolve_policy_from_ssot(self) -> dict[str, Any] | None:
        """
        Resolve policy from AuditorContext.policies (SSOT only).

        IMPORTANT:
        - If policy_file is None (Option B), this resolves by scanning policies for
          at least one of the bound rule IDs.
        """
        policies = getattr(self.context, "policies", None)
        if not isinstance(policies, dict):
            logger.warning("AuditorContext.policies is missing or invalid.")
            return None

        # 1) If we have a policy_file hint, try hint-based resolution first.
        if self.__class__.policy_file is not None:
            for key in self._policy_lookup_hints():
                candidate = policies.get(key)
                if isinstance(candidate, dict):
                    return candidate

            hint_stem = Path(str(self.__class__.policy_file)).stem.lower()
            if hint_stem:
                for candidate in policies.values():
                    if not isinstance(candidate, dict):
                        continue
                    pid = str(
                        candidate.get("id") or candidate.get("policy_id") or ""
                    ).lower()
                    if pid and (pid.endswith(hint_stem) or hint_stem in pid):
                        return candidate

        # 2) Option B fallback: find a policy that declares at least one bound rule id.
        wanted = set(self._bound_rule_ids)
        if wanted:
            for candidate in policies.values():
                if not isinstance(candidate, dict):
                    continue
                rules = candidate.get("rules")
                if not isinstance(rules, list):
                    continue
                if self._policy_contains_any_rule_id(rules, wanted):
                    return candidate

        return None

    @staticmethod
    def _policy_contains_any_rule_id(rules: Iterable[Any], wanted: set[str]) -> bool:
        for r in rules:
            if isinstance(r, dict) and r.get("id") in wanted:
                return True
        return False
