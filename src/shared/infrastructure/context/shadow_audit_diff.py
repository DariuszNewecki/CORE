# src/shared/infrastructure/context/shadow_audit_diff.py

"""
ShadowAuditDiff — diff between two constitutional audit result sets.

Surfaces the consequences of proposed (uncommitted) changes at audit-finding
granularity: which constitutional findings the shadow audit introduces that
the disk audit didn't have, which the shadow resolves, and which persist
unchanged.

This is the load-bearing pain receptor for V2.3-REBIRTH Limbs (Octopus paper
§3 — "Chemosensory Context", tasting consequences before commit). The signal
is constitutional by construction: the diff is grounded in the same rule set
the Governor uses to authorize work, so a non-empty `new_findings()` is by
definition "the limb's proposed change would introduce constitutional harm
the system already disallows."

Constitutional alignment:
- Pillar II (UNIX Neuron): pure function over two audit result dicts. No I/O.
- Pillar III (Functional Governance): the Governor's audit IS the Limb's
  pain receptor; reflex loops will consume this diff to terminate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Findings are fingerprinted by (check_id, file_path, line_number). Severity
# and message are intentionally not part of the fingerprint: a rule's message
# may embed line text or other surface-detail that drifts spuriously when the
# file shifts; check_id+file+line is the stable identity of "the same finding
# fired at the same spot."
_FindingKey = tuple[str, str | None, int | None]


# ID: 2fe62cb6-c99f-447b-a66e-49a017f99a23
@dataclass(frozen=True)
class FindingRef:
    """Lightweight reference to a single audit finding."""

    check_id: str
    severity: str
    file_path: str | None
    line_number: int | None
    message: str


# ID: 6f373fdc-8925-40f6-b9ab-ae263ac9e857
class ShadowAuditDiff:
    """Compute the diff between two audit result sets.

    Both inputs are lists of finding dicts in the shape produced by
    AuditFinding.as_dict() — that is, dicts carrying at minimum::

        {"check_id": str, "severity": str, "message": str,
         "file_path": str | None, "line_number": int | None, ...}

    The dict shape is what run_stateless_audit() places in the "findings"
    field of its return value, so callers can pass those payloads directly.
    """

    # ID: 598f0ced-70cf-487c-995a-11026faca347
    def __init__(
        self,
        disk_findings: list[dict[str, Any]],
        shadow_findings: list[dict[str, Any]],
    ):
        self._disk_index: dict[_FindingKey, dict[str, Any]] = {
            self._key(f): f for f in disk_findings
        }
        self._shadow_index: dict[_FindingKey, dict[str, Any]] = {
            self._key(f): f for f in shadow_findings
        }

    # ID: 5a1ea26a-b3fd-4c07-90b6-095f98d5f7e8
    def new_findings(self) -> list[FindingRef]:
        """Findings the shadow audit reports that the disk audit did not.

        This is the primary pain signal: "your proposed change would introduce
        these constitutional violations."
        """
        new_keys = self._shadow_index.keys() - self._disk_index.keys()
        return sorted(
            (self._to_ref(self._shadow_index[k]) for k in new_keys),
            key=self._sort_key,
        )

    # ID: 031250ae-fb86-49db-93b8-ff37c45498e2
    def resolved_findings(self) -> list[FindingRef]:
        """Findings the disk audit reports that the shadow audit does not.

        Tells the limb "your proposed change cleared these existing
        violations." A future reflex loop terminates honestly when
        new_findings() is empty AND at least one resolved finding is present,
        avoiding the "no harm done but also no good done" trivial-fix trap.
        """
        gone_keys = self._disk_index.keys() - self._shadow_index.keys()
        return sorted(
            (self._to_ref(self._disk_index[k]) for k in gone_keys),
            key=self._sort_key,
        )

    # ID: e5080b92-3b0c-41a5-ac28-7da761354a28
    def unchanged_findings(self) -> list[FindingRef]:
        """Findings present in both audits at the same (check_id, file, line).

        The proposed change neither introduced nor resolved these. Returned
        for completeness; not load-bearing for the reflex loop.
        """
        shared = self._disk_index.keys() & self._shadow_index.keys()
        return sorted(
            (self._to_ref(self._shadow_index[k]) for k in shared),
            key=self._sort_key,
        )

    # ID: 99378722-cab2-4958-901e-5639107ca150
    def is_clean(self) -> bool:
        """True iff the shadow audit introduces no new findings.

        Note: this is "the proposed change does not make things worse," NOT
        "the proposed change fixes anything." Check resolved_findings() for
        the latter when the limb's mission was remediation.
        """
        return not self.new_findings()

    @staticmethod
    def _key(finding: dict[str, Any]) -> _FindingKey:
        return (
            str(finding.get("check_id", "")),
            finding.get("file_path"),
            finding.get("line_number"),
        )

    @staticmethod
    def _to_ref(finding: dict[str, Any]) -> FindingRef:
        return FindingRef(
            check_id=str(finding.get("check_id", "")),
            severity=str(finding.get("severity", "")),
            file_path=finding.get("file_path"),
            line_number=finding.get("line_number"),
            message=str(finding.get("message", "")),
        )

    @staticmethod
    def _sort_key(ref: FindingRef) -> tuple[str, str, int]:
        # Stable ordering: by check_id, then file_path, then line. None values
        # sort first so context-level findings appear consistently.
        return (ref.check_id, ref.file_path or "", ref.line_number or 0)


__all__ = ["FindingRef", "ShadowAuditDiff"]
