# src/will/workers/violation_executor.py
# ID: will.workers.violation_executor
"""
ViolationExecutorWorker - Discovery path for unmapped rules.

Will-layer acting worker. Claims open audit violation findings whose rules
have no active RemediationMap entry, delegates the LLM remediation ceremony
to ViolationRemediator (Body layer), and surfaces AtomicAction candidates
to the Blackboard after each successful fix.

Constitutional role in the remediation system:

    RemediatorWorker (Will)     — Handles MAPPED rules → Proposals
    ViolationExecutorWorker     — Handles UNMAPPED rules → Candidates   ← THIS
    ViolationRemediator (Body)  — Performs ceremony for both paths

RemediatorWorker has priority. It runs first and claims findings whose rules
are mapped. ViolationExecutorWorker claims only what remains — findings whose
rules have no active RemediationMap entry (confidence >= 0.80).

The primary output is not a fixed file. It is an AtomicAction candidate —
evidence that a particular LLM-reasoned fix worked for a particular rule,
surfaced on the Blackboard for human review and eventual codification.

When a rule is codified into an AtomicAction and added to the RemediationMap,
it graduates to RemediatorWorker and ViolationExecutorWorker never touches it
again. Reducing this worker's workload to zero means CORE has fully codified
its remediation knowledge.

See: .intent/papers/CORE-ViolationExecutor.md
     .intent/papers/CORE-OptimizerWorker.md

Constitutional standing:
- Declaration:      .intent/workers/violation_executor.yaml
- Class:            acting
- Phase:            execution
- Permitted tools:  llm.remote_coder, file.read, crate.create,
                    canary.validate, crate.apply, git.commit
- Approval:         true (inherited from ViolationRemediator ceremony)

LAYER: will/workers — acting worker. Delegates all execution ceremony to
body.workers.violation_remediator.ViolationRemediator.process_file().
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_FINDING_SUBJECT_PREFIX = "audit.violation::"
_CANDIDATE_SUBJECT = "audit.remediation.candidate"
_CLAIM_LIMIT = 50


# ID: ba3704d8-23da-49d2-b67d-7b42f33fce83
class ViolationExecutorWorker(Worker):
    """
    Acting worker. Discovery path for rules with no RemediationMap entry.

    Claims open audit violation findings for unmapped rules, delegates
    the full LLM + Crate + Canary ceremony to ViolationRemediator (Body),
    and surfaces AtomicAction candidates on the Blackboard after success.

    Args:
        core_context: Initialized CoreContext.
        write: If False, dry-run mode — ceremony runs but no files are changed.
    """

    declaration_name = "violation_executor"

    def __init__(self, core_context: Any, write: bool = False) -> None:
        super().__init__()
        self._ctx = core_context
        self._write = write

    # ID: 4cb3dadb-8f63-4da1-8725-c88bcf819d3b
    async def run(self) -> None:
        """
        Main cycle. Steps 1-10 from CORE-ViolationExecutor.md.
        """
        # Step 1: Heartbeat
        await self.post_heartbeat()

        mode = "WRITE" if self._write else "DRY-RUN"
        logger.info("ViolationExecutorWorker: starting [%s]", mode)

        # Step 2: Load RemediationMap — determine which rules are already mapped
        mapped_rule_ids = self._load_mapped_rule_ids()
        logger.info(
            "ViolationExecutorWorker: %d rule(s) mapped in RemediationMap.",
            len(mapped_rule_ids),
        )

        # Steps 1-2 (claim): Claim open findings for unmapped rules only
        findings = await self._claim_unmapped_findings(mapped_rule_ids)

        if not findings:
            await self.post_report(
                subject="violation_executor.run.complete",
                payload={
                    "write": self._write,
                    "message": "No open unmapped violation findings.",
                    "mapped_rule_count": len(mapped_rule_ids),
                },
            )
            logger.info(
                "ViolationExecutorWorker: no unmapped findings — nothing to do."
            )
            return

        logger.info(
            "ViolationExecutorWorker: claimed %d unmapped finding(s) [%s].",
            len(findings),
            mode,
        )

        # Step 2 (group): Group by file_path
        by_file: dict[str, list[dict[str, Any]]] = {}
        for finding in findings:
            payload = finding.get("payload") or {}
            file_path = str(payload.get("file_path") or "").strip()
            if not file_path:
                logger.warning(
                    "ViolationExecutorWorker: skipping finding %s — missing file_path",
                    finding.get("entry_id"),
                )
                continue
            by_file.setdefault(file_path, []).append(finding)

        logger.info(
            "ViolationExecutorWorker: %d finding(s) across %d file(s) [%s].",
            len(findings),
            len(by_file),
            mode,
        )

        succeeded = 0
        failed = 0
        candidates_surfaced = 0

        # Steps 3-10: Process each file
        for file_path, file_findings in by_file.items():
            ok, handled_rule_ids = await self._process_file(
                file_path, file_findings, mapped_rule_ids
            )
            if ok:
                succeeded += 1
                # Step 10: Surface candidate for each handled rule
                for rule_id in handled_rule_ids:
                    await self._surface_candidate(rule_id, file_path)
                    candidates_surfaced += 1
            else:
                failed += 1

        await self.post_report(
            subject="violation_executor.run.complete",
            payload={
                "write": self._write,
                "claimed": len(findings),
                "files": len(by_file),
                "succeeded": succeeded,
                "failed": failed,
                "candidates_surfaced": candidates_surfaced,
            },
        )
        logger.info(
            "ViolationExecutorWorker: done [%s] — %d succeeded, %d failed, %d candidates.",
            mode,
            succeeded,
            failed,
            candidates_surfaced,
        )

    # -------------------------------------------------------------------------
    # Per-file orchestration
    # -------------------------------------------------------------------------

    # ID: 0cd4ad14-321d-418c-8ac0-9f79d4f8c29a
    async def _process_file(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        mapped_rule_ids: set[str],
    ) -> tuple[bool, list[str]]:
        """
        Steps 3-9 for a single file.

        Returns (success, list_of_rule_ids_processed).
        """
        # Step 4: RemediationMap gate — race condition check.
        # If any finding's rule became mapped AFTER we claimed it,
        # release those findings back to open for RemediatorWorker.
        late_mapped = [
            f
            for f in findings
            if str((f.get("payload") or {}).get("rule") or "") in mapped_rule_ids
        ]
        if late_mapped:
            await self._release_findings(late_mapped)
            findings = [f for f in findings if f not in late_mapped]
            logger.info(
                "ViolationExecutorWorker: released %d finding(s) back to open "
                "(RemediationMap gate — late-mapped rule).",
                len(late_mapped),
            )

        if not findings:
            # All findings for this file were late-mapped and released.
            return False, []

        # Collect rule IDs from this file's findings (for candidate surfacing)
        rule_ids = sorted(
            {str((f.get("payload") or {}).get("rule") or "unknown") for f in findings}
        )

        # Steps 5-9: Delegate full ceremony to ViolationRemediator (Body layer).
        # One LLM invocation covers all violations in this file.
        # target_rule: single rule if one, semicolon-joined if multiple.
        target_rule = rule_ids[0] if len(rule_ids) == 1 else "; ".join(rule_ids)

        try:
            from body.workers.violation_remediator import ViolationRemediator

            remediator = ViolationRemediator(
                core_context=self._ctx,
                target_rule=target_rule,
                write=self._write,
            )
            ok = await remediator.process_file(file_path, findings)
            return ok, rule_ids if ok else []

        except Exception as exc:
            logger.error(
                "ViolationExecutorWorker: ceremony failed for '%s' — %s",
                file_path,
                exc,
            )
            await self._abandon_findings(findings)
            return False, []

    # -------------------------------------------------------------------------
    # Step 10: Surface candidate
    # -------------------------------------------------------------------------

    # ID: 14ff66a6-3e70-480b-9a97-d35327621c2f
    async def _surface_candidate(self, rule_id: str, file_path: str) -> None:
        """
        Step 10: Post an AtomicAction candidate to the Blackboard.

        This is the primary discovery output of ViolationExecutorWorker.
        OptimizerWorker (once implemented) will consume these candidates.
        Until then, the human architect monitors them directly.

        Subject: audit.remediation.candidate::{rule_id}
        """
        try:
            await self.post_report(
                subject=f"{_CANDIDATE_SUBJECT}::{rule_id}",
                payload={
                    "rule_id": rule_id,
                    "file_path": file_path,
                    "worker": "violation_executor",
                    "note": (
                        "AtomicAction candidate. A fix for this rule was "
                        "successfully produced by LLM and validated by Canary. "
                        "If this pattern recurs, codify it as an AtomicAction "
                        "and add to RemediationMap to graduate this rule to "
                        "RemediatorWorker. See CORE-ViolationExecutor.md §4."
                    ),
                },
            )
            logger.info(
                "ViolationExecutorWorker: candidate surfaced — rule='%s' file='%s'",
                rule_id,
                file_path,
            )
        except Exception as exc:
            # Candidate surfacing is best-effort — failure does not invalidate the fix.
            logger.warning(
                "ViolationExecutorWorker: candidate surfacing failed for rule '%s': %s",
                rule_id,
                exc,
            )

    # -------------------------------------------------------------------------
    # RemediationMap loader
    # -------------------------------------------------------------------------

    # ID: a533cee7-1062-4ec0-9fd3-693e3152406d
    def _load_mapped_rule_ids(self) -> set[str]:
        """
        Load the set of rule IDs with active RemediationMap entries.

        Delegates to _load_remediation_map() from body.autonomy.audit_analyzer
        via PathResolver — the same pattern used by ViolationRemediatorWorker.
        Never hardcodes paths or structure.

        Returns empty set on any load error (safe fallback: treat all rules
        as unmapped and claim all violation findings).
        """
        try:
            from body.autonomy.audit_analyzer import _load_remediation_map
            from shared.path_resolver import PathResolver

            path_resolver = PathResolver(self._ctx.git_service.repo_path)
            remediation_map = _load_remediation_map(path_resolver)
            return set(remediation_map.keys())
        except Exception as exc:
            logger.warning(
                "ViolationExecutorWorker: could not load RemediationMap (%s). "
                "Proceeding with empty mapped set — all violation findings eligible.",
                exc,
            )
            return set()

    # -------------------------------------------------------------------------
    # Blackboard helpers
    # -------------------------------------------------------------------------

    # ID: 4788d491-6c2d-4222-9cd8-14b063c7a0ec
    async def _claim_unmapped_findings(
        self, mapped_rule_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Atomically claim open audit.violation findings for unmapped rules."""
        try:
            from body.services.service_registry import service_registry

            svc = await service_registry.get_blackboard_service()
            return await svc.claim_unmapped_violation_findings(
                mapped_rule_ids=mapped_rule_ids,
                limit=_CLAIM_LIMIT,
                claimed_by=self._worker_uuid,
            )
        except Exception as exc:
            logger.error(
                "ViolationExecutorWorker: claim_unmapped_violation_findings failed — %s",
                exc,
            )
            return []

    # ID: b3b9c33a-d475-413d-b963-2363bbb4bf84
    async def _release_findings(self, findings: list[dict[str, Any]]) -> None:
        """Release claimed findings back to open status."""
        try:
            from body.services.service_registry import service_registry

            svc = await service_registry.get_blackboard_service()
            entry_ids = [str(f["entry_id"]) for f in findings]
            await svc.release_claimed_entries(entry_ids)
        except Exception as exc:
            logger.error(
                "ViolationExecutorWorker: release_claimed_entries failed — %s", exc
            )

    # ID: a4fb50f5-af70-45b4-a40b-56ff94d1d937
    async def _abandon_findings(self, findings: list[dict[str, Any]]) -> None:
        """Mark findings abandoned after an unrecoverable ceremony failure."""
        try:
            from body.services.service_registry import service_registry

            svc = await service_registry.get_blackboard_service()
            entry_ids = [str(f["entry_id"]) for f in findings]
            await svc.abandon_entries(entry_ids)
        except Exception as exc:
            logger.error("ViolationExecutorWorker: abandon_entries failed — %s", exc)
