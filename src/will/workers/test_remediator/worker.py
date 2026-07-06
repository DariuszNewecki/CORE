# src/will/workers/test_remediator/worker.py
"""
TestRemediatorWorker - Routes test signals to autonomous test generation.

Constitutional role: acting worker, remediation phase.

Responsibility (from .intent/workers/test_remediator.yaml):
  Consume open `python::test.runner.missing` and `python::test.runner.failure`
  findings from the Blackboard (ADR-091 D2 canonical subject format). For each
  source_file, call TestGapEvaluator (ADR-133 D1/D2) to identify which public
  symbols lack test coverage. Create one flow.build_test_for_symbol proposal per
  untested symbol (ADR-133 D3/D4). Dedup and circuit-break per (source_file,
  symbol_name) pair.

The autonomous test loop this participates in:

  TestRunnerSensor (sensing)
      posts python::test.runner.missing::<source_file> and
            python::test.runner.failure::<test_file>::<test_name> findings
          ↓
  TestRemediatorWorker (acting)  ← THIS WORKER
      reads open findings from Blackboard
      groups findings by source_file
      calls TestGapEvaluator per source_file → GapReport
      creates one flow.build_test_for_symbol proposal per untested symbol
      defers findings to first symbol proposal (CORE-Finding.md §7 / ADR-010)
          ↓
  ProposalConsumerWorker
      executes APPROVED proposals via ProposalExecutor
          ↓
  TestRunnerSensor runs again
      confirms the test is now present / passing

Design constraints:
- No LLM calls (TestGapEvaluator is AST-only)
- No direct file writes
- Dedup is per (source_file, symbol_name) pair
- File-level circuit breaker (inherited count) applies before gap evaluation
- Per-symbol circuit breaker (proposal failures) applies per symbol
- Defers Blackboard entries to the FIRST symbol proposal so the §7a revival
  path in ProposalStateManager.mark_failed preserves the Finding→Proposal link
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker

from ._operations import (
    _abandon_capped_findings,
    _create_symbol_proposal,
    _defer_to_proposal,
    _get_active_symbol_proposals,
    _inherit_attempt_count,
    _load_open_findings,
    _query_recent_symbol_failures,
    _query_source_file_attempt_count,
    _release_entries,
)


logger = getLogger(__name__)


# ID: e9f2a4b6-c1d8-4e3f-9a5b-7c8d1e2f3a4b
class TestRemediatorWorker(Worker):
    """
    Acting worker that converts Blackboard test findings into per-symbol proposals.

    Claims open `python::test.runner.missing` and `python::test.runner.failure`
    findings (ADR-091 D2), calls TestGapEvaluator per source_file, and creates
    one flow.build_test_for_symbol proposal per untested public symbol (ADR-133 D4).
    Dedup and circuit-breaking operate at (source_file, symbol_name) granularity.
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
        Core work unit (ADR-133 D4):
        1. Claim open python::test.runner.missing + python::test.runner.failure findings
        2. Group findings by payload["source_file"]
        3. For each source_file:
           a. File-level circuit breaker: abandon immediately if inherited count >= cap_n
           b. Call TestGapEvaluator → GapReport (AST-only, no LLM)
           c. If no gaps: post test.coverage.complete, release findings
           d. For each untested symbol:
              - Dedup skip if active flow.build_test_for_symbol proposal exists
              - Per-symbol circuit breaker: skip if recent symbol failures >= cap_n
              - Create flow.build_test_for_symbol proposal
           e. Defer findings to first created proposal
        4. Post blackboard report
        """
        from pathlib import Path

        from body.evaluators.test_gap_evaluator import TestGapEvaluator
        from shared.infrastructure.intent.operational_config import (
            load_operational_config,
        )

        cap_n = load_operational_config().blackboard.remediation_cap_n

        repo_root: Path | None = None
        if self._core_context is not None:
            try:
                repo_root = self._core_context.git_service.repo_path
            except Exception:
                pass
        if repo_root is None:
            from shared.infrastructure.paths import resolve_default_repo_path

            repo_root = resolve_default_repo_path()

        await self.post_heartbeat()

        open_findings = await _load_open_findings(self._worker_uuid)

        if not open_findings:
            logger.info("TestRemediatorWorker: no open test findings")
            return

        logger.info(
            "TestRemediatorWorker: %d open findings to process",
            len(open_findings),
        )

        by_source: dict[str, list[dict[str, Any]]] = {}
        for finding in open_findings:
            source_file = (finding.get("payload") or {}).get("source_file")
            if not source_file:
                continue
            by_source.setdefault(source_file, []).append(finding)

        active_symbol_proposals = await _get_active_symbol_proposals()
        evaluator = TestGapEvaluator(repo_root=repo_root)

        proposals_created: list[str] = []
        source_files_skipped: list[str] = []
        entries_deferred: int = 0
        entries_released: int = 0
        proposals_skipped_cap: int = 0
        symbols_skipped_dedup: int = 0

        for source_file, findings in by_source.items():
            entry_ids = [f["id"] for f in findings]

            # File-level circuit breaker: inherited abandoned count.
            inherited = await _query_source_file_attempt_count(source_file)
            if inherited >= cap_n:
                abandoned_ids = await _abandon_capped_findings(entry_ids, inherited)
                proposals_skipped_cap += 1
                # Stable subject (source_file path, not finding UUID) — prevents one
                # unique cap_reached subject per sensor cycle from flooding F-19's
                # created_24h/stuck_24h counts. The first appearance sets first_seen;
                # subsequent posts to the same subject leave first_seen unchanged.
                if abandoned_ids:
                    await self.post_observation(
                        subject=f"blackboard.remediation_cap_reached::{source_file}",
                        payload={
                            "source_file": source_file,
                            "reason": "remediation_cap_exhausted_via_inheritance",
                            "remediation_cap_n": cap_n,
                            "inherited_count": inherited,
                            "abandoned_entry_ids": abandoned_ids,
                        },
                        status="abandoned",
                    )
                logger.warning(
                    "TestRemediatorWorker: '%s' — file-level cap exhausted "
                    "(inherited=%d, cap=%d); %d finding(s) abandoned",
                    source_file,
                    inherited,
                    cap_n,
                    len(abandoned_ids),
                )
                continue

            # Gap evaluation (ADR-133 D1/D2): AST-only, no LLM.
            gap_result = await evaluator.execute(source_file=source_file)

            if not gap_result.ok:
                error = gap_result.data.get("error", "unknown")
                logger.warning(
                    "TestRemediatorWorker: gap evaluation failed for '%s': %s — "
                    "abandoning findings; source must be fixed before tests can be generated",
                    source_file,
                    error,
                )
                abandoned_ids = await _abandon_capped_findings(entry_ids, inherited)
                if abandoned_ids:
                    await self.post_observation(
                        subject=f"blackboard.remediation_cap_reached::{source_file}",
                        payload={
                            "source_file": source_file,
                            "reason": "gap_evaluation_failed",
                            "error": error,
                            "abandoned_entry_ids": abandoned_ids,
                        },
                        status="abandoned",
                    )
                proposals_skipped_cap += 1
                continue

            gaps = gap_result.data.get("gaps", [])
            test_file = gap_result.data.get("test_file", "")

            if not gaps:
                logger.info(
                    "TestRemediatorWorker: '%s' — no gaps found (%d already covered); "
                    "releasing findings",
                    source_file,
                    gap_result.data.get("covered_count", 0),
                )
                await self.post_observation(
                    subject=f"test.coverage.complete::{source_file}",
                    payload={
                        "source_file": source_file,
                        "covered_count": gap_result.data.get("covered_count", 0),
                    },
                    status="resolved",
                )
                entries_released += await _release_entries(entry_ids)
                source_files_skipped.append(source_file)
                continue

            # Per-symbol proposals (ADR-133 D3/D4).
            first_proposal_id: str | None = None
            symbols_created_this_file = 0

            for gap in gaps:
                symbol_name = gap["name"]
                symbol_kind = gap["kind"]
                signature = gap["signature"]
                sym_key = (source_file, symbol_name)

                if sym_key in active_symbol_proposals:
                    symbols_skipped_dedup += 1
                    logger.debug(
                        "TestRemediatorWorker: skipping '%s::%s' — "
                        "active proposal exists",
                        source_file,
                        symbol_name,
                    )
                    continue

                sym_failures = await _query_recent_symbol_failures(
                    source_file, symbol_name
                )
                if sym_failures >= cap_n:
                    proposals_skipped_cap += 1
                    logger.warning(
                        "TestRemediatorWorker: '%s::%s' — per-symbol cap reached "
                        "(failures=%d, cap=%d); skipping",
                        source_file,
                        symbol_name,
                        sym_failures,
                        cap_n,
                    )
                    continue

                proposal_id = await _create_symbol_proposal(
                    source_file=source_file,
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    signature=signature,
                    test_file=test_file,
                    findings=findings,
                )

                if proposal_id:
                    proposals_created.append(f"{source_file}::{symbol_name}")
                    symbols_created_this_file += 1
                    if first_proposal_id is None:
                        first_proposal_id = proposal_id
                    logger.info(
                        "TestRemediatorWorker: created symbol proposal '%s' for %s::%s",
                        proposal_id,
                        source_file,
                        symbol_name,
                    )

            # Defer findings to the first symbol proposal for this source_file
            # so the §7a revival path preserves the Finding→Proposal link.
            if first_proposal_id:
                if inherited > 0:
                    await _inherit_attempt_count(entry_ids, inherited)
                entries_deferred += await _defer_to_proposal(
                    entry_ids, first_proposal_id
                )
            elif symbols_created_this_file == 0:
                entries_released += await _release_entries(entry_ids)

        await self.post_report(
            subject="test_remediator.completed",
            payload={
                "open_findings": len(open_findings),
                "source_files": len(by_source),
                "proposals_created": len(proposals_created),
                "proposals_skipped_dedup": len(source_files_skipped),
                "proposals_skipped_cap": proposals_skipped_cap,
                "symbols_skipped_dedup": symbols_skipped_dedup,
                "entries_deferred": entries_deferred,
                "entries_released": entries_released,
                "created_proposals": proposals_created,
                "skipped_source_files": source_files_skipped,
            },
        )

        logger.info(
            "TestRemediatorWorker: done — %d proposals created, %d source_files "
            "skipped (no gaps), %d skipped (cap), %d symbols skipped (dedup), "
            "%d entries deferred, %d entries released",
            len(proposals_created),
            len(source_files_skipped),
            proposals_skipped_cap,
            symbols_skipped_dedup,
            entries_deferred,
            entries_released,
        )
