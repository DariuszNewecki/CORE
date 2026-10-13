# src/will/audit_violation/staleness.py
"""Guard against auditing stale code.

The daemon audits CORE's clone, which fast-forwards along the merge branch
(RepoSync, CORE_UPSTREAM_BRANCH). On 2026-10-12 the clone followed a branch
nobody merged to any more and every audit for a day judged old code while
the governor's queue waited on fixes already deployed. Each audit cycle now
records the commit it audited; a clone that stays behind the fetched merge
branch for two consecutive cycles raises one blocking finding for the
governor, resolved by the first cycle that is current again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

STALE_SUBJECT = "audit.stale_code::clone"
STALE_AFTER_CYCLES = 2


@dataclass(frozen=True)
# ID: 6a846346-268c-482a-bd20-b7e5dd72e2c0
class AuditedCommit:
    """The commit an audit cycle judged, against the merge branch's head."""

    audited: str | None
    upstream: str | None

    @property
    # ID: 9ff3a141-5312-4cfe-9939-d37dd0c4bca2
    def behind(self) -> bool:
        """True when the merge branch has commits the audited tree lacks."""
        return bool(self.audited and self.upstream and self.audited != self.upstream)

    # ID: b0e8c4e2-8018-41df-88ab-36c9e267fd9d
    def as_payload(self) -> dict[str, Any]:
        """The fields every audit report carries."""
        return {
            "audited_commit": self.audited,
            "upstream_commit": self.upstream,
            "behind_upstream": self.behind,
        }


# ID: 5e28abd4-87fa-403c-b2ac-9bfefd7b4a61
def audited_commit(git_service: Any, branch: str) -> AuditedCommit:
    """HEAD of the audited tree and the locally fetched head of ``branch``.

    Either is None when unknown (no git, never fetched); ``behind`` is then
    False: the guard only speaks when it can compare. A HEAD ahead of the
    branch (CORE's own unpushed commits) is not behind.
    """
    try:
        head = git_service.get_current_commit()
        upstream = git_service.resolve_ref(f"refs/remotes/upstream/{branch}")
    except Exception as exc:  # the guard must never break an audit
        logger.debug("staleness: cannot read commits: %s", exc)
        return AuditedCommit(None, None)
    if not isinstance(head, str) or not isinstance(upstream, str):
        return AuditedCommit(head if isinstance(head, str) else None, None)
    if head != upstream and git_service.is_ancestor(upstream, head):
        upstream = head  # ahead of the branch: current
    return AuditedCommit(head, upstream)


# ID: fe7ddbc7-24e9-4606-875a-75701dd1818c
async def guard_stale_audit(
    worker: Any, blackboard: Any, state: AuditedCommit, behind_cycles: int
) -> None:
    """Raise the stale-code finding once, after STALE_AFTER_CYCLES cycles
    behind; resolve it when the audited tree is current again."""
    active = await blackboard.fetch_active_finding_subjects_by_prefix(STALE_SUBJECT)
    if state.behind:
        if behind_cycles >= STALE_AFTER_CYCLES and STALE_SUBJECT not in active:
            await worker.post_observation(
                subject=STALE_SUBJECT,
                payload={
                    **state.as_payload(),
                    "severity": "block",
                    "cycles_behind": behind_cycles,
                    "message": (
                        "The daemon is auditing a commit behind the merge branch: "
                        "findings reflect old code until CORE's clone catches up."
                    ),
                },
                status="indeterminate",
            )
        return
    if STALE_SUBJECT in active:
        await blackboard.adjudicate_indeterminate_findings(
            subject_prefix=STALE_SUBJECT,
            current_violation_subjects=set(),
            resolved_by="audit_violation_sensor",
        )
