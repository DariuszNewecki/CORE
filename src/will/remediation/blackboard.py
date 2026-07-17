# src/will/remediation/blackboard.py
"""
RemediationBlackboard — the capability RemediationCeremony depends on to
post and record outcomes, instead of depending on a concrete Worker.

ADR-153 D2. The ceremony (originally ViolationRemediator's own methods)
called self.post_report(...)/self.post_observation(...) directly (Worker
base) and self._mark_findings(...)/self._post_failed(...) (BlackboardMixin,
itself calling self.post_report internally). Extracting the ceremony to a
non-Worker service means it can no longer reach those methods via `self`.
A capability Protocol lets it depend on "something that can post and
record outcomes" instead of a Worker type — the same move that resolves
the constitutional violation this ADR exists to fix (a Worker holding a
reference to another Worker).

Two implementations:
- WorkerRemediationBlackboard wraps a real Worker + CoreContext. Backs the
  executor path (ViolationExecutorWorker) and the CLI rule-mode path
  (ViolationRemediator.run()) — both post under the wrapped worker's own,
  genuinely-registered identity. No UUID substitution.
- NullRemediationBlackboard backs CLI file-mode (remediate.py), which has
  no real blackboard findings to claim or mark and, after this ADR, no
  Worker instance at all on this path. Every method is a true no-op —
  this is a deliberate behavior change from today (file-mode currently
  posts real heartbeat/observation/report entries under its own identity
  via the monkeypatched Worker.start()/run() path), recorded in ADR-153's
  Consequences, not silently dropped.
"""

from __future__ import annotations

from typing import Any, Protocol

from shared.logger import getLogger


logger = getLogger(__name__)

_FAILED_SUBJECT = "audit.remediation.failed"


class _Poster(Protocol):
    """The narrow slice of Worker this module actually wraps."""

    # ID: e4eb2c77-4b36-41e5-886e-e0c4f6ff8b17
    async def post_report(self, subject: str, payload: dict[str, Any]) -> Any: ...

    # ID: 70c597d7-456f-4e62-873a-584cd4895054
    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> Any: ...


# ID: 5d396ae9-1353-42e0-a3ba-c584f128eac4
class RemediationBlackboard(Protocol):
    """Capability RemediationCeremony depends on for every blackboard
    interaction. See module docstring for the two concrete shapes."""

    # ID: e86f3b10-4776-4a3f-a343-2c3ff89eae52
    async def post_report(self, subject: str, payload: dict[str, Any]) -> Any: ...

    # ID: de3f2d97-0d57-42e6-bfc3-af5edc96945e
    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> Any: ...

    # ID: 20e7cacb-7d83-4e50-8dcb-b99d6a3fd1e6
    async def mark_findings(
        self, findings: list[dict[str, Any]], status: str
    ) -> None: ...

    # ID: b3d1e3bd-bfe7-45ac-a030-f8635d6ecc90
    async def post_failed(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        target_rule: str | None,
        write: bool,
        reason: str,
    ) -> None: ...


# ID: 7dc3a952-fbaa-4543-8de8-04c88486d610
class WorkerRemediationBlackboard:
    """Real implementation, backing the executor and CLI rule-mode paths.

    Wraps a real, registered Worker (whichever one is calling —
    ViolationExecutorWorker or ViolationRemediator itself) for posting,
    and CoreContext's blackboard service for marking. Every post/mark
    lands under the wrapped worker's own identity — no UUID substitution.
    """

    def __init__(self, worker: _Poster, core_context: Any) -> None:
        self._worker = worker
        self._ctx = core_context

    # ID: 55efc059-9953-4689-9e27-c16f96cee474
    async def post_report(self, subject: str, payload: dict[str, Any]) -> Any:
        return await self._worker.post_report(subject, payload)

    # ID: 6dad8584-7e6b-4312-8608-bdd1174f5a7e
    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> Any:
        return await self._worker.post_observation(subject, payload, status=status)

    # ID: b850fd8b-0478-45b0-8a53-00305660e5a3
    async def mark_findings(self, findings: list[dict[str, Any]], status: str) -> None:
        """Batch-update status of a list of findings."""
        bb = await self._ctx.registry.get_blackboard_service()
        if status == "abandoned":
            # Must go through the count-incrementing path (ADR-104 D9): plain
            # update_entry_status() leaves remediation_attempt_count NULL, so
            # the circuit breaker in ViolationExecutorWorker always reads 0
            # and the sensor->remediator->abandon loop runs unbounded.
            entry_ids = [str(f["id"]) for f in findings]
            await bb.abandon_entries_and_increment_attempt_count(entry_ids)
        else:
            for finding in findings:
                await bb.update_entry_status(finding["id"], status)

    # ID: b9bc6122-7dff-44ca-81a0-efb1fe2f3cf5
    async def post_failed(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        target_rule: str | None,
        write: bool,
        reason: str,
    ) -> None:
        """Post a failure record to the blackboard.

        Uses post_report (entry_type='report') rather than post_finding
        (entry_type='finding') because a failed remediation is an
        informational record, not an actionable work item.
        """
        await self.post_report(
            subject=f"{_FAILED_SUBJECT}::{file_path}",
            payload={
                "file_path": file_path,
                "rule": target_rule,
                "reason": reason,
                "write": write,
                "finding_ids": [finding["id"] for finding in findings],
            },
        )


# ID: 9259845b-0e17-473d-a80c-631d2cb5eb79
class NullRemediationBlackboard:
    """No-op implementation, backing CLI file-mode.

    Every method is a true no-op. No blackboard entry of any kind is
    posted for this path — see the module docstring and ADR-153
    Consequences for why this is a deliberate, recorded behavior change
    rather than an oversight.
    """

    # ID: 9019428b-837e-4ef1-807e-d43dd38711b6
    async def post_report(self, subject: str, payload: dict[str, Any]) -> None:
        return None

    # ID: 82f463e0-273f-4369-8088-7155161196d1
    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> None:
        return None

    # ID: 85415504-1738-4ff3-85b9-915bfabbd4be
    async def mark_findings(self, findings: list[dict[str, Any]], status: str) -> None:
        return None

    # ID: 7844f1c0-d880-4037-b0ae-be51035b04f2
    async def post_failed(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        target_rule: str | None,
        write: bool,
        reason: str,
    ) -> None:
        return None
