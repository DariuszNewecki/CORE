# src/will/workers/test_remediator/worker.py
"""
TestRemediatorWorker - Routes test signals to autonomous test generation.

Constitutional role: acting worker, remediation phase.

Responsibility (from .intent/workers/test_remediator.yaml):
  Consume open `python::test.runner.missing` and `python::test.runner.failure`
  findings from the Blackboard (ADR-091 D2 canonical subject format) and
  create one flow.build_tests proposal per distinct source_file to drive
  autonomous test generation. Every claimed finding is routed to the single
  'flow.build_tests' flow (ADR-046 D2) — no remediation map lookup, no
  unmappable or delegate split.

The autonomous test loop this participates in:

  TestRunnerSensor (sensing)
      posts python::test.runner.missing::<source_file> and
            python::test.runner.failure::<test_file>::<test_name> findings
          ↓
  TestRemediatorWorker (acting)  ← THIS WORKER
      reads open findings from Blackboard
      groups findings by source_file
      creates one Proposal per source_file (deduped per source_file)
      defers findings to the proposal (CORE-Finding.md §7 / ADR-010)
          ↓
  ProposalConsumerWorker
      executes APPROVED proposals via ProposalExecutor
          ↓
  TestRunnerSensor runs again
      confirms the test is now present / passing

Design constraints:
- No LLM calls
- No direct file writes
- Dedup is per source_file — two concurrent flow.build_tests proposals
  for different source files are valid and must not block each other
- Never creates a second proposal for a source_file that already has an
  active 'flow.build_tests' proposal
- Defers Blackboard entries to the proposal AFTER the proposal for their
  source_file is persisted (not before). The §7a revival path in
  ProposalStateManager.mark_failed depends on this Finding→Proposal
  linkage being recorded in payload.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker

from ._operations import (
    _TARGET_FLOW_ID,
    _create_proposal,
    _defer_to_proposal,
    _get_active_build_tests_source_files,
    _inherit_attempt_count,
    _load_open_findings,
    _query_source_file_attempt_count,
    _release_entries,
)


logger = getLogger(__name__)


# ID: e9f2a4b6-c1d8-4e3f-9a5b-7c8d1e2f3a4b
class TestRemediatorWorker(Worker):
    """
    Acting worker that converts Blackboard test findings into flow.build_tests proposals.

    Claims open `python::test.runner.missing` and `python::test.runner.failure`
    findings (ADR-091 D2; both sub_namespaces filtered through the
    test-remediation predicate), groups them by source_file, and creates one
    'flow.build_tests' proposal per source_file. Dedup is per source_file —
    two concurrent flow.build_tests proposals for different source files are
    valid and must not block each other.
    """

    __test__ = False

    declaration_name = "test_remediator"

    def __init__(
        self, core_context: Any = None, declaration_name: str = "", **kwargs: Any
    ) -> None:
        """Accept daemon kwargs — stores core_context for symmetry with siblings."""
        super().__init__(declaration_name=declaration_name)
        self._core_context = core_context

    # ID: f1a3b5c7-d2e4-4f6a-8b9c-1d2e3f4a5b6c
    async def run(self) -> None:
        """
        Core work unit:
        1. Claim open python::test.runner.missing + python::test.runner.failure findings
        2. Group findings by payload["source_file"]
        3. For each group: check per-source_file dedup against active
           flow.build_tests proposals; create a proposal and defer that
           group's findings to it on success, or release that group's
           findings on dedup skip
        4. Post blackboard report
        """
        open_findings = await _load_open_findings(self._worker_uuid)

        if not open_findings:
            await self.post_heartbeat()
            logger.info("TestRemediatorWorker: no open test findings")
            return

        logger.info(
            "TestRemediatorWorker: %d open findings to process",
            len(open_findings),
        )

        # Group findings by source_file. _load_open_findings guarantees
        # every finding has a non-empty payload["source_file"], but we
        # defensively skip any that slipped through.
        by_source: dict[str, list[dict[str, Any]]] = {}
        for finding in open_findings:
            source_file = (finding.get("payload") or {}).get("source_file")
            if not source_file:
                continue
            by_source.setdefault(source_file, []).append(finding)

        active_source_files = await _get_active_build_tests_source_files()

        proposals_created: list[str] = []
        source_files_skipped: list[str] = []
        entries_deferred: int = 0
        entries_released: int = 0

        for source_file, findings in by_source.items():
            if source_file in active_source_files:
                logger.info(
                    "TestRemediatorWorker: skipping '%s' — active "
                    "flow.build_tests proposal exists for this source_file",
                    source_file,
                )
                source_files_skipped.append(source_file)
                released = await _release_entries([f["id"] for f in findings])
                entries_released += released
                continue

            proposal_id = await _create_proposal(_TARGET_FLOW_ID, findings)

            if proposal_id:
                proposals_created.append(source_file)
                # ADR-104 D9: carry the remediation_attempt_count forward
                # from any prior abandoned findings for this source_file so
                # the cap is not silently bypassed when sensors re-detect
                # the same unresolved test and post fresh findings at count=0.
                inherited = await _query_source_file_attempt_count(source_file)
                if inherited > 0:
                    await _inherit_attempt_count([f["id"] for f in findings], inherited)
                # ADR-010 / CORE-Finding.md §7: on successful proposal
                # creation, transition findings to 'deferred_to_proposal'
                # and store proposal_id in their payload. The §7a revival
                # contract in ProposalStateManager.mark_failed depends on
                # this linkage.
                deferred = await _defer_to_proposal(
                    [f["id"] for f in findings], proposal_id
                )
                entries_deferred += deferred
                logger.info(
                    "TestRemediatorWorker: created proposal '%s' for flow '%s' "
                    "source_file='%s' (%d findings, %d entries deferred to proposal)",
                    proposal_id,
                    _TARGET_FLOW_ID,
                    source_file,
                    len(findings),
                    deferred,
                )

        await self.post_report(
            subject="test_remediator.completed",
            payload={
                "open_findings": len(open_findings),
                "source_files": len(by_source),
                "proposals_created": len(proposals_created),
                "source_files_skipped_dedup": len(source_files_skipped),
                "entries_deferred": entries_deferred,
                "entries_released": entries_released,
                "created_for_source_files": proposals_created,
                "skipped_source_files": source_files_skipped,
            },
        )

        logger.info(
            "TestRemediatorWorker: done — %d proposals created across %d "
            "source file group(s), %d skipped (dedup), %d entries deferred, "
            "%d entries released",
            len(proposals_created),
            len(by_source),
            len(source_files_skipped),
            entries_deferred,
            entries_released,
        )
