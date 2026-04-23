# src/mind/governance/violation_report.py
"""
Violation reporting structures for constitutional enforcement.

Used by IntentGuard and engines to report policy violations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
# ID: eaac12b5-8310-469a-a89d-d6047e2fbc54
class ViolationReport:
    """
    Detailed violation report with remediation context.

    Attributes:
        rule_name: Rule identifier that was violated
        path: File path (repo-relative) where violation occurred
        message: Human-readable violation description
        severity: "error" or "warning"
        suggested_fix: Optional remediation guidance
        source_policy: Policy file that declared this rule
    """

    rule_name: str
    path: str
    message: str
    severity: str
    suggested_fix: str = ""
    source_policy: str = "unknown"


# ID: b0bc85fe-cc5b-4547-b2ae-cb6540e8df66
class ConstitutionalViolationError(ValueError):
    """
    Raised when IntentGuard rejects a proposed file operation.

    Carries the structured list of ViolationReport objects for diagnostic
    persistence downstream (e.g. in ``ActionResult.data`` → proposal
    ``execution_results``). Prior to this enrichment, FileHandler raised a
    bare ``ValueError`` whose message preserved only the first violation's
    free-text description — ``path``, ``rule_name``, ``source_policy``, and
    any subsequent violations were lost on the persistence hop, forcing
    diagnostic triage to happen via live daemon probes instead of recorded
    evidence.

    Contract:
    - Inherits from ValueError. Every previous call site raised a bare
      ValueError with the same semantic, so existing ``except ValueError``
      and ``except Exception`` handlers continue to catch this unchanged.
    - ``str(self)`` preserves the legacy ``"Blocked by IntentGuard: {msg}"``
      one-liner verbatim so downstream handlers that stringify the exception
      (e.g. action bodies populating ``ActionResult.data["error"]``) behave
      byte-identically to before. This is a widening of the contract, not
      a breaking change.
    - Handlers that want the structured violations can call ``to_dict()``
      for JSON-safe serialization into ``execution_results``, or access
      ``self.violations`` directly for programmatic use.
    """

    def __init__(self, violations: list[ViolationReport]) -> None:
        self.violations: list[ViolationReport] = list(violations)
        primary = self.violations[0] if self.violations else None
        detail = primary.message if primary else "constitutional rule violated"
        super().__init__(f"Blocked by IntentGuard: {detail}")

    # ID: bb7ea640-fae1-4688-9a5d-38bd52b8ec10
    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for persistence into execution_results.

        Shape is intentionally flat-per-violation with primitive values only —
        no nested dataclasses, no objects — so it survives ``json.dumps``
        without custom encoders. The top-level ``error`` key preserves the
        legacy flat-string form so older readers of execution_results that
        expect ``data["error"]`` continue to work.
        """
        return {
            "error": str(self),
            "blocked_by": "IntentGuard",
            "violation_count": len(self.violations),
            "violations": [
                {
                    "rule_name": v.rule_name,
                    "path": v.path,
                    "severity": v.severity,
                    "source_policy": v.source_policy,
                    "message": v.message,
                    "suggested_fix": v.suggested_fix,
                }
                for v in self.violations
            ],
        }
