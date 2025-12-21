# src/mind/governance/checks/rule_required_fields_check.py
"""
Constitutional audit check: validates that all declared rules in .intent
contain the mandatory fields required by CORE's rule format.

This prevents "soft drift" where new policies declare rules but omit fields
needed for deterministic enforcement coverage, auditing, and tooling.

Targets:
- rules.required_fields
- rules.must_have_statement
- rules.no_placeholder_ids
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, ClassVar

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


@dataclass(frozen=True)
class _RuleRef:
    """Normalized rule reference from a policy document."""

    policy_key: str
    rule_id: str
    raw: dict[str, Any]


# ID: 8aee0c42-2104-4251-934b-9cfbc865876e
class RuleRequiredFieldsCheck(BaseCheck):
    """
    Ensures every declared rule object has the required fields
    and that rule IDs are non-empty and non-placeholder.
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "rules.required_fields",
        "rules.must_have_statement",
        "rules.no_placeholder_ids",
    ]

    # Minimum viable "flat rule" contract keys
    _REQUIRED_KEYS: ClassVar[set[str]] = {"id", "statement", "enforcement"}

    # Common placeholders that should never ship in .intent
    _PLACEHOLDER_TOKENS: ClassVar[set[str]] = {
        "tbd",
        "todo",
        "unknown",
        "placeholder",
        "xxx",
    }

    _TOKEN_SPLIT_RE: ClassVar[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")

    # ID: 9a6766eb-760a-497b-8afb-bfd74c2730fc
    def execute(self) -> list[AuditFinding]:
        policies = getattr(self.context, "policies", None) or {}
        if not isinstance(policies, dict) or not policies:
            return [
                AuditFinding(
                    check_id="rules.required_fields",
                    severity=AuditSeverity.WARNING,
                    message="No policies available in audit context; cannot validate rule structures.",
                    file_path=".intent",
                    context={
                        "suggestion": "Ensure auditor loads .intent policies into context.policies."
                    },
                )
            ]

        findings: list[AuditFinding] = []
        for rule_ref in self._iter_rules(policies):
            findings.extend(self._validate_rule(rule_ref))
        return findings

    def _iter_rules(self, policies: dict[str, Any]) -> Iterable[_RuleRef]:
        """
        Iterate all rule objects across loaded policy documents.

        Expects each policy to be dict-like and optionally contain a list under key "rules".
        """
        for policy_key, policy_doc in policies.items():
            if not isinstance(policy_doc, dict):
                continue

            rules = policy_doc.get("rules")
            if not isinstance(rules, list):
                continue

            for rule in rules:
                if not isinstance(rule, dict):
                    # Malformed rule object
                    yield _RuleRef(
                        policy_key=str(policy_key),
                        rule_id="<non-dict>",
                        raw={"rule": rule},
                    )
                    continue

                rid = str(rule.get("id", "")).strip() if "id" in rule else ""
                yield _RuleRef(
                    policy_key=str(policy_key),
                    rule_id=rid or "<missing>",
                    raw=rule,
                )

    def _validate_rule(self, rr: _RuleRef) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        policy_key = rr.policy_key
        rule_id = rr.rule_id
        rule_obj = rr.raw

        file_path = f".intent (policy_key={policy_key})"

        # 0) Malformed rule object (non-dict wrapper case)
        if rule_id == "<non-dict>":
            findings.append(
                AuditFinding(
                    check_id="rules.required_fields",
                    severity=AuditSeverity.ERROR,
                    message="Policy rules list contains a non-dict entry; each rule must be a mapping/object.",
                    file_path=file_path,
                    context={
                        "policy_key": policy_key,
                        "raw_rule": rule_obj.get("rule"),
                    },
                )
            )
            return findings

        # 1) Required keys must exist (presence, not truthiness)
        missing_keys = [k for k in sorted(self._REQUIRED_KEYS) if k not in rule_obj]
        if missing_keys:
            findings.append(
                AuditFinding(
                    check_id="rules.required_fields",
                    severity=AuditSeverity.ERROR,
                    message=f"Rule is missing required key(s): {', '.join(missing_keys)}",
                    file_path=file_path,
                    context={
                        "policy_key": policy_key,
                        "rule_id": rule_id,
                        "missing_keys": missing_keys,
                    },
                )
            )
            return findings

        # 2) Validate id
        rid = str(rule_obj.get("id", "")).strip()
        if not rid:
            findings.append(
                AuditFinding(
                    check_id="rules.required_fields",
                    severity=AuditSeverity.ERROR,
                    message="Rule id is empty.",
                    file_path=file_path,
                    context={"policy_key": policy_key, "rule_id": rule_id},
                )
            )
            return findings  # downstream checks depend on a usable id

        # 3) Validate statement
        statement = str(rule_obj.get("statement", "")).strip()
        if not statement:
            findings.append(
                AuditFinding(
                    check_id="rules.must_have_statement",
                    severity=AuditSeverity.ERROR,
                    message="Rule statement is empty.",
                    file_path=file_path,
                    context={"policy_key": policy_key, "rule_id": rid},
                )
            )

        # 4) Validate enforcement field (presence already checked)
        enforcement = rule_obj.get("enforcement")
        if enforcement is None:
            findings.append(
                AuditFinding(
                    check_id="rules.required_fields",
                    severity=AuditSeverity.ERROR,
                    message="Rule enforcement is null; enforcement must be defined.",
                    file_path=file_path,
                    context={"policy_key": policy_key, "rule_id": rid},
                )
            )

        # 5) Validate ID is not placeholder (token-based)
        rid_lower = rid.lower()
        tokens = [t for t in self._TOKEN_SPLIT_RE.split(rid_lower) if t]
        if any(t in self._PLACEHOLDER_TOKENS for t in tokens):
            findings.append(
                AuditFinding(
                    check_id="rules.no_placeholder_ids",
                    severity=AuditSeverity.ERROR,
                    message=f"Rule id '{rid}' appears to be a placeholder.",
                    file_path=file_path,
                    context={
                        "policy_key": policy_key,
                        "rule_id": rid,
                        "tokens": tokens,
                    },
                )
            )

        return findings
