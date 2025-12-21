# src/mind/governance/checks/safety_brain_protection_check.py

"""
Enforces the CORE "you cannot silently rewrite the brain" controls.

Targets:
- safety.immutable_constitution
- safety.deny_core_loop_edit
- safety.change_must_be_logged

This check is intentionally two-layer:
1) Verifies the Safety Standard declares the rule + protected_paths (SSOT integrity)
2) Verifies runtime enforcement exists (IntentGuard denies writes for protected paths)
   and that write-paths exhibit auditable intent metadata (IntentBundle ID).

Until runtime enforcement is wired, this check will FAIL (truthfully), which is
what we want for constitutional hardening.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from will.orchestration.intent_guard import IntentGuard


logger = getLogger(__name__)


# ID: 6d6d2a0b-57c0-4e8a-b7f4-12f6f5c7f1a1
class SafetyBrainProtectionCheck(BaseCheck):
    """
    Ensures that constitutional safety rules protecting CORE's brain are:
    - declared in the Safety Standard (SSOT), and
    - enforced by runtime guardrails (IntentGuard), and
    - supported by auditable intent metadata in write-paths.
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "safety.immutable_constitution",
        "safety.deny_core_loop_edit",
        "safety.change_must_be_logged",
    ]

    # Legacy-only reference (kept for message compatibility)
    _LEGACY_SAFETY_STANDARD_PATH = ".intent/charter/standards/operations/safety.json"

    # ID: 053fef99-26fb-4d83-b127-f6070e0b11fd
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        standard = self._get_safety_standard()
        if standard is None:
            findings.append(
                AuditFinding(
                    check_id="safety.immutable_constitution",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "Safety Standard missing in SSOT (AuditorContext). "
                        f"Legacy path reference: {self._LEGACY_SAFETY_STANDARD_PATH}"
                    ),
                    file_path="SSOT:auditor_context.policies",
                    context={
                        "expected_policy_hints": [
                            "standard_operations_safety",
                            "safety",
                            "operations/safety",
                        ],
                    },
                )
            )
            return findings

        rules = standard.get("rules", [])
        if not isinstance(rules, list):
            findings.append(
                AuditFinding(
                    check_id="safety.immutable_constitution",
                    severity=AuditSeverity.ERROR,
                    message="Safety Standard invalid: 'rules' must be a list.",
                    file_path=self._policy_identity_for_evidence(standard),
                )
            )
            return findings

        by_id = {
            str(r.get("id")): r
            for r in rules
            if isinstance(r, dict) and isinstance(r.get("id"), str)
        }

        # --- 1) SSOT integrity: rule declared + protected_paths present where required ---
        findings.extend(
            self._require_rule(by_id, "safety.immutable_constitution", standard)
        )
        findings.extend(
            self._require_rule(by_id, "safety.deny_core_loop_edit", standard)
        )
        findings.extend(
            self._require_rule(by_id, "safety.change_must_be_logged", standard)
        )

        protected_a = self._protected_paths(by_id.get("safety.immutable_constitution"))
        protected_b = self._protected_paths(by_id.get("safety.deny_core_loop_edit"))

        if not protected_a:
            findings.append(
                AuditFinding(
                    check_id="safety.immutable_constitution",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "Safety rule 'safety.immutable_constitution' must declare non-empty protected_paths."
                    ),
                    file_path=self._policy_identity_for_evidence(standard),
                )
            )

        if not protected_b:
            findings.append(
                AuditFinding(
                    check_id="safety.deny_core_loop_edit",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "Safety rule 'safety.deny_core_loop_edit' must declare non-empty protected_paths."
                    ),
                    file_path=self._policy_identity_for_evidence(standard),
                )
            )

        # --- 2) Runtime enforcement: IntentGuard should deny writes to protected paths ---
        guard = IntentGuard(repo_path=self.repo_root)

        for rel in protected_a:
            findings.extend(
                self._expect_denied(
                    guard=guard,
                    rule_id="safety.immutable_constitution",
                    rel_path=rel,
                    standard=standard,
                )
            )

        for rel in protected_b:
            findings.extend(
                self._expect_denied(
                    guard=guard,
                    rule_id="safety.deny_core_loop_edit",
                    rel_path=rel,
                    standard=standard,
                )
            )

        # --- 3) Auditable intent: change_must_be_logged must be implementable ---
        findings.extend(self._check_write_paths_reference_intent_bundle())

        return findings

    def _get_safety_standard(self) -> dict[str, Any] | None:
        """
        Resolve the Safety Standard via the AuditorContext SSOT.

        We do not assume a single key; we use prioritized lookup then fallback scan.
        """
        # Canonical interface: BaseCheck always has self.context (AuditorContext)
        auditor_ctx = getattr(self, "context", None)
        if auditor_ctx is None:
            logger.warning(
                "BaseCheck has no context; cannot resolve SSOT policy resources."
            )
            return None

        policies = getattr(auditor_ctx, "policies", None)
        if not isinstance(policies, dict):
            logger.warning("AuditorContext.policies is missing or invalid.")
            return None

        preferred_keys = (
            "standard_operations_safety",
            "operations_safety",
            "safety",
            "operations/safety",
            "policies/operations/safety",
        )
        for key in preferred_keys:
            candidate = policies.get(key)
            if isinstance(candidate, dict):
                return candidate

        # Fallback: scan loaded resources for something that looks like the operations safety standard.
        for _k, candidate in policies.items():
            if not isinstance(candidate, dict):
                continue

            pid = str(candidate.get("id") or candidate.get("policy_id") or "").lower()
            title = str(candidate.get("title") or "").lower()

            # SSOT conventions: prefer explicit IDs, but allow title heuristics
            if "safety" in pid and "operations" in pid:
                return candidate
            if "safety" in title and ("operations" in title or "runtime" in title):
                return candidate

        return None

    def _policy_identity_for_evidence(self, standard: dict[str, Any]) -> str:
        """
        SSOT-loaded policy objects may not retain filesystem paths; return stable ID for evidence.
        """
        pid = standard.get("id") or standard.get("policy_id") or "unknown_policy"
        return f"SSOT:{pid}"

    def _require_rule(
        self,
        by_id: dict[str, dict],
        rule_id: str,
        standard: dict[str, Any],
    ) -> list[AuditFinding]:
        if rule_id not in by_id:
            return [
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=f"Safety Standard missing rule '{rule_id}'.",
                    file_path=self._policy_identity_for_evidence(standard),
                )
            ]
        return []

    def _protected_paths(self, rule: dict | None) -> list[str]:
        if not rule or not isinstance(rule, dict):
            return []
        paths = rule.get("protected_paths", [])
        if not isinstance(paths, list):
            return []
        out: list[str] = []
        for p in paths:
            if isinstance(p, str) and p.strip():
                out.append(p.strip())
        return out

    def _expect_denied(
        self,
        *,
        guard: IntentGuard,
        rule_id: str,
        rel_path: str,
        standard: dict[str, Any],
    ) -> list[AuditFinding]:
        norm_rel = str(Path(rel_path).as_posix()).lstrip("/")

        try:
            ok, violations = guard.check_transaction([norm_rel])

            if ok:
                return [
                    AuditFinding(
                        check_id=rule_id,
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"IntentGuard allows write to protected path '{norm_rel}'. "
                            "This violates the Safety Standard; protected paths must be denied unless routed through the "
                            "human-in-the-loop amendment mechanism."
                        ),
                        file_path=norm_rel,
                        context={
                            "source_policy": self._policy_identity_for_evidence(
                                standard
                            ),
                            "intent_guard_violations": violations,
                        },
                    )
                ]

            return []

        except Exception as exc:
            return [
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=f"IntentGuard enforcement test failed for '{norm_rel}': {exc}",
                    file_path=norm_rel,
                    context={
                        "source_policy": self._policy_identity_for_evidence(standard)
                    },
                )
            ]

    def _check_write_paths_reference_intent_bundle(self) -> list[AuditFinding]:
        """
        First-stage enforcement for safety.change_must_be_logged.
        """
        targets = [
            Path("src/body/cli/logic/proposal_service.py"),
            Path("src/features/autonomy/micro_proposal_executor.py"),
        ]
        missing: list[str] = []

        needles = ("intent_bundle", "IntentBundle", "bundle_id", "intent_bundle_id")

        for rel in targets:
            abs_path = self.repo_root / rel
            if not abs_path.exists():
                continue
            try:
                text = abs_path.read_text(encoding="utf-8")
            except Exception:
                continue

            if not any(n in text for n in needles):
                missing.append(str(rel))

        if missing:
            return [
                AuditFinding(
                    check_id="safety.change_must_be_logged",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "Write-paths do not reference an IntentBundle identifier. "
                        "At minimum, proposal apply / executor paths must carry and log an IntentBundle ID before writing."
                    ),
                    file_path="; ".join(missing),
                    context={"required_any_of": list(needles)},
                )
            ]
        return []
