# src/body/workers/violation_remediator/worker.py
# ID: body.workers.violation_remediator
"""
ViolationRemediator - Constitutional Compliance Acting Worker.

Responsibility: For each open audit violation finding on the blackboard,
build a deterministic architectural context package for the violating file
(evidence only, not authority), invoke RemoteCoder (Grok) via PromptModel
to produce a fix, validate via Crate/Canary ceremony, and apply to live
src/ with a git commit.

Phase discipline:
  RUNTIME phase  — _plan_file():  read source, build architectural context,
                                  validate confidence, decide whether to proceed.
  EXECUTION phase — _execute_file(): LLM invocation, Crate, Canary, apply, commit.

These phases are separated. Indeterminate planning outcomes block execution.

Dry-run safety chain:
  - write=False -> planning runs (confidence-gated)
  - write=False -> LLM runs, proposed fix is produced
  - write=False -> Crate is created (packed) but NOT applied
  - write=False -> Canary runs on the Crate (validates without applying)
  - write=False -> No git commit
  - write=False -> Blackboard entry posted as status='dry_run_complete'
                   with full proposed fix for human review
  - write=True  -> Full ceremony: apply + commit

Failure discipline:
  - Brief build failure       -> indeterminate -> halt, do NOT proceed
  - Low role confidence       -> indeterminate -> halt in write mode
  - git commit failure        -> abandoned    -> return False (not "resolved")
  - Any exception in ceremony -> abandoned    -> return False

Constitutional standing:
- Declaration:      .intent/workers/violation_remediator.yaml
- Class:            acting
- Phase:            execution
- Permitted tools:  llm.remote_coder, file.read, crate.create,
                    canary.validate, crate.apply, git.commit
- Approval:         true

LAYER: body/workers - acting worker. Receives CoreContext via constructor
injection. All src/ writes via ActionExecutor -> Crate -> Canary -> apply.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.self_healing.remediation_interpretation.service import (
    RemediationInterpretationError,
    RemediationInterpretationService,
)
from shared.workers.base import Worker

from .blackboard import BlackboardMixin
from .ceremony import CeremonyMixin
from .context import ContextMixin
from .llm import LLMMixin
from .models import _RemediationPlan


logger = getLogger(__name__)

_COMPLETE_SUBJECT = "audit.remediation.complete"
_DRY_RUN_SUBJECT = "audit.remediation.dry_run"

# Minimum role detection confidence required to proceed in write mode.
_MIN_ROLE_CONFIDENCE_FOR_WRITE = 0.55


# ID: bb52f62a-45c9-47a4-9ff8-788b0c6ca4f1
class ViolationRemediator(
    BlackboardMixin, CeremonyMixin, ContextMixin, LLMMixin, Worker
):
    """
    Acting worker. Claims open audit violation findings from the blackboard,
    builds a deterministic architectural context package (evidence, not law)
    for the violating file, invokes RemoteCoder (Grok) via PromptModel to
    produce a fix, then runs the full Crate/Canary ceremony.

    In dry-run mode (write=False): planning, LLM, and Canary run,
    nothing is applied, proposed fix is posted to the blackboard for human
    review.

    In write mode (write=True): full ceremony - apply + git commit.

    One Crate per file - all violations in a file are fixed in a single
    LLM invocation to preserve coherence and minimise API cost.

    Args:
        core_context: Initialized CoreContext.
        target_rule: Only process findings for this rule ID.
        write: If False, dry-run mode - no src/ writes, no commits.
    """

    declaration_name = "violation_remediator_body"

    def __init__(
        self,
        core_context: Any,
        target_rule: str | None = None,
        write: bool = False,
    ) -> None:
        super().__init__()
        self._ctx = core_context
        self._target_rule = target_rule
        self._write = write
        self._interpretation_service = RemediationInterpretationService()

    # ID: vr-run-001
    # ID: 83141abe-9611-497f-a14c-29c5cf04d305
    async def run(self) -> None:
        """
        Main execution loop. Groups findings by file, processes each file
        through the full remediation ceremony (or dry-run variant).
        """
        await self.post_heartbeat()

        mode = "WRITE" if self._write else "DRY-RUN"
        logger.info(
            "ViolationRemediator: starting [%s] for rule '%s'",
            mode,
            self._target_rule,
        )

        findings = await self._claim_open_findings()

        if not findings:
            await self.post_report(
                subject="violation_remediator.run.complete",
                payload={
                    "rule": self._target_rule,
                    "write": self._write,
                    "processed": 0,
                    "message": "No open violation findings to remediate.",
                },
            )
            logger.info("ViolationRemediator: no open findings.")
            return

        by_file: dict[str, list[dict[str, Any]]] = {}
        for finding in findings:
            payload = finding.get("payload") or {}
            file_path = str(payload.get("file_path") or "").strip()

            if not file_path:
                logger.warning(
                    "ViolationRemediator: skipping finding %s with missing file_path",
                    finding.get("id"),
                )
                continue

            by_file.setdefault(file_path, []).append(finding)

        logger.info(
            "ViolationRemediator: %d findings across %d files [%s].",
            len(findings),
            len(by_file),
            mode,
        )

        succeeded = 0
        failed = 0

        for file_path, file_findings in by_file.items():
            ok = await self._process_file(file_path, file_findings)
            if ok:
                succeeded += 1
            else:
                failed += 1

        await self.post_report(
            subject="violation_remediator.run.complete",
            payload={
                "rule": self._target_rule,
                "write": self._write,
                "succeeded": succeeded,
                "failed": failed,
                "message": f"[{mode}] {succeeded} files processed, {failed} failed.",
            },
        )
        logger.info(
            "ViolationRemediator: [%s] %d succeeded, %d failed.",
            mode,
            succeeded,
            failed,
        )

    # -------------------------------------------------------------------------
    # Top-level per-file orchestration
    # -------------------------------------------------------------------------

    # ID: 0bc3eb6a-ecab-4c52-843b-90084d336782
    async def process_file(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
    ) -> bool:
        """
        Public entry point for per-file ceremony.

        Called by ViolationExecutorWorker (Will layer) after it has already
        claimed findings and performed the RemediationMap gate check.
        Delegates to _process_file — the full RUNTIME + EXECUTION ceremony.

        This is the Will → Body delegation interface for file remediation.
        """
        return await self._process_file(file_path, findings)

    async def _process_file(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
    ) -> bool:
        """
        Orchestrate the two-phase ceremony for a single file.

        RUNTIME phase:  _plan_file()    — read, interpret, gate confidence
        EXECUTION phase: _execute_file() — LLM, crate, canary, apply, commit
        """
        plan = await self._plan_file(file_path, findings)
        if plan is None:
            return False

        return await self._execute_file(file_path, findings, plan)

    # -------------------------------------------------------------------------
    # RUNTIME phase — planning
    # -------------------------------------------------------------------------

    async def _plan_file(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
    ) -> _RemediationPlan | None:
        """
        RUNTIME phase: read the source file and build the architectural
        context package. Validates confidence before returning.

        Returns None (and marks findings indeterminate) if:
        - the source file cannot be read
        - the architectural context service raises
        - role confidence is below threshold in write mode

        This method intentionally performs NO execution-phase actions.
        """
        repo_root = self._ctx.git_service.repo_path
        abs_path = repo_root / file_path

        try:
            original_source = abs_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "ViolationRemediator: cannot read %s - %s",
                file_path,
                exc,
            )
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, f"Cannot read file: {exc}")
            return None

        try:
            baseline_sha = self._ctx.git_service.get_current_commit()
        except RuntimeError as exc:
            logger.warning(
                "ViolationRemediator: git checkpoint failed - %s",
                exc,
            )
            baseline_sha = "unknown"

        try:
            architectural_context = (
                self._interpretation_service.build_reasoning_brief_dict(
                    file_path=file_path,
                    source_code=original_source,
                    findings=findings,
                )
            )
        except RemediationInterpretationError as exc:
            logger.warning(
                "ViolationRemediator: architectural context failed for %s - %s "
                "[indeterminate — halting]",
                file_path,
                exc,
            )
            await self._mark_findings(findings, "indeterminate")
            await self._post_failed(
                file_path,
                findings,
                f"Architectural context indeterminate: {exc}",
            )
            return None

        role_confidence = (
            architectural_context.get("file_role", {}).get("confidence", 0.0) or 0.0
        )
        if self._write and role_confidence < _MIN_ROLE_CONFIDENCE_FOR_WRITE:
            logger.warning(
                "ViolationRemediator: role confidence %.2f < %.2f for %s "
                "[indeterminate in write mode — halting]",
                role_confidence,
                _MIN_ROLE_CONFIDENCE_FOR_WRITE,
                file_path,
            )
            await self._mark_findings(findings, "indeterminate")
            await self._post_failed(
                file_path,
                findings,
                (
                    f"Role confidence {role_confidence:.2f} below write threshold "
                    f"{_MIN_ROLE_CONFIDENCE_FOR_WRITE}. Human review required."
                ),
            )
            return None

        logger.info(
            "ViolationRemediator: plan ready for %s "
            "(role=%s, confidence=%.2f, recommended=%s)",
            file_path,
            architectural_context.get("file_role", {}).get("role_id", "unknown"),
            role_confidence,
            (architectural_context.get("recommended_strategy") or {}).get(
                "strategy_id", "none"
            ),
        )

        violations_summary = self._build_violations_summary(findings)
        context_text = await self._build_context(file_path, violations_summary)

        return _RemediationPlan(
            file_path=file_path,
            original_source=original_source,
            baseline_sha=baseline_sha,
            violations_summary=violations_summary,
            architectural_context=architectural_context,
            context_text=context_text,
        )

    # -------------------------------------------------------------------------
    # EXECUTION phase — ceremony
    # -------------------------------------------------------------------------

    async def _execute_file(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        plan: _RemediationPlan,
    ) -> bool:
        """
        EXECUTION phase: LLM proposal, Crate, Canary, apply, commit.

        plan.architectural_context is passed to the LLM as advisory
        evidence, labelled explicitly as 'architectural_context' — not as
        a planning directive. The LLM's obligation is to satisfy the rule,
        not to follow the brief.
        """
        # Gate: if all finding rules have a mapped atomic action in the
        # remediation map, this worker must not handle them — they belong
        # to the constitutional path (RemediatorWorker). Release the claims
        # back to open so RemediatorWorker can pick them up on its next run.
        mapped_action = self._check_atomic_action_coverage(findings)
        if mapped_action is not None:
            logger.info(
                "ViolationRemediator: all rules for %s are covered by atomic "
                "action '%s' — releasing findings to open for RemediatorWorker",
                file_path,
                mapped_action,
            )
            bb = await self._ctx.registry.get_blackboard_service()
            finding_ids = [f["id"] for f in findings]
            await bb.release_claimed_entries(finding_ids)
            return False

        if self._write:
            self._archive_rollback(file_path, plan.original_source, plan.baseline_sha)

        proposed_fix = await self._invoke_llm(
            file_path=file_path,
            source_code=plan.original_source,
            context_text=plan.context_text,
            violations_summary=plan.violations_summary,
            architectural_context=plan.architectural_context,
        )
        if proposed_fix is None:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, "LLM fix failed")
            return False

        crate_id = await self._pack_crate(file_path, proposed_fix)
        if crate_id is None:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, "Crate creation failed")
            return False

        await self._align_staged_file(crate_id, file_path)

        canary_passed = await self._run_canary(crate_id)
        if not canary_passed:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(
                file_path,
                findings,
                f"Canary failed for crate {crate_id}",
            )
            return False

        if not self._write:
            await self.post_finding(
                subject=f"{_DRY_RUN_SUBJECT}::{file_path}",
                payload={
                    "file_path": file_path,
                    "rule": self._target_rule,
                    "crate_id": crate_id,
                    "baseline_sha": plan.baseline_sha,
                    "canary_passed": canary_passed,
                    "proposed_fix": proposed_fix,
                    "violations_count": len(findings),
                    "architectural_context": plan.architectural_context,
                    "message": (
                        "Dry-run complete. Canary passed. "
                        "Review 'proposed_fix' and 'architectural_context' "
                        "then re-run with write=True."
                    ),
                },
            )
            await self._mark_findings(findings, "dry_run_complete")
            logger.info(
                "ViolationRemediator: [DRY-RUN] %s - canary passed, fix ready.",
                file_path,
            )
            return True

        # --- write mode: apply then commit ---

        try:
            from body.services.crate_processing_service import CrateProcessingService

            service = CrateProcessingService(self._ctx)
            await service.apply_and_finalize_crate(crate_id)
        except Exception as exc:
            logger.warning(
                "ViolationRemediator: apply_and_finalize failed for %s - %s",
                crate_id,
                exc,
            )
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, f"Apply failed: {exc}")
            return False

        # Commit MUST succeed before findings are marked resolved.
        # A failed commit means the repo and the blackboard would disagree
        # about whether the fix is live. That is a data integrity failure.
        try:
            self._ctx.git_service.commit(
                f"fix({self._target_rule}): autonomous remediation in {file_path}"
            )
        except RuntimeError as exc:
            logger.error(
                "ViolationRemediator: git commit FAILED for %s - %s "
                "[marking abandoned — fix is applied but uncommitted]",
                file_path,
                exc,
            )
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(
                file_path,
                findings,
                f"Git commit failed after apply: {exc}. "
                "Fix is applied to disk but NOT committed. Manual intervention required.",
            )
            return False

        await self.post_finding(
            subject=f"{_COMPLETE_SUBJECT}::{file_path}",
            payload={
                "file_path": file_path,
                "rule": self._target_rule,
                "crate_id": crate_id,
                "baseline_sha": plan.baseline_sha,
                "violations_fixed": len(findings),
                "architectural_context": plan.architectural_context,
            },
        )
        await self._mark_findings(findings, "resolved")

        logger.info(
            "ViolationRemediator: [WRITE] applied %s (crate=%s, rule=%s)",
            file_path,
            crate_id,
            self._target_rule,
        )
        return True
