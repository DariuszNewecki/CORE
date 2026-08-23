# src/will/remediation/ceremony.py
"""
RemediationCeremony — the extracted LLM/Crate/Canary/commit ceremony,
originally ViolationRemediator's own process_file/_plan_file/_execute_file.

ADR-153. Extracted so ViolationExecutorWorker (and CLI file-mode) no
longer need to import and instantiate ViolationRemediator — a Worker
subclass — to run this ceremony, which is exactly the constitutional
violation architecture.workers.no_direct_worker_import exists to prevent.

The ceremony was already a self-contained, parameterized, claim-
independent unit before this extraction — its own docstring called
process_file "the Will -> Body delegation interface for file remediation,"
called after the caller has already claimed findings and performed the
RemediationMap gate check. This class makes that independence structural:
it takes a RemediationBlackboard (ADR-153 D2) instead of being a Worker
itself, so posting/marking is attributed to whichever real identity the
caller supplies — never borrowed via a caller_uuid substitution.

Phase discipline (unchanged from the original):
  RUNTIME phase  — _plan_file():  read source, build architectural context,
                                  validate confidence, decide whether to proceed.
  EXECUTION phase — _execute_file(): LLM invocation, Crate, Canary, apply, commit.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from body.services.fix_run_service import submit_and_persist_fix
from body.services.proposal_submission_service import (
    ProposalSubmissionError,
    submit_ceremony_proposal,
)
from body.services.validated_candidate_service import build_validated_candidate
from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.models.validated_remediation_candidate import CandidateConstructionError
from will.autonomy.proposal_factory import build_assisted_lane_draft_proposal
from will.autonomy.proposal_mapper import ProposalMapper
from will.self_healing.remediation_interpretation.service import (
    RemediationInterpretationError,
    RemediationInterpretationService,
)

from .blackboard import RemediationBlackboard
from .context import ContextMixin
from .crate_canary import CrateCanaryMixin
from .llm import LLMMixin
from .models import _RemediationPlan


logger = getLogger(__name__)

_DRY_RUN_SUBJECT = "audit.remediation.dry_run"
_COMPLETE_SUBJECT = "audit.remediation.complete"
_DRAFT_SUBJECT = "audit.remediation.draft_created"

_CFG = load_operational_config().workers.violation_remediator


# ID: 295e67f1-bffc-4925-8d1c-161e0337d591
class RemediationCeremony(CrateCanaryMixin, ContextMixin, LLMMixin):
    """
    The full per-file remediation ceremony: build architectural context,
    invoke RemoteCoder (Grok) via PromptModel to produce a fix, then run
    the Crate/Canary/apply/commit ceremony.

    In dry-run mode (write=False): planning, LLM, and Canary run,
    nothing is applied, proposed fix is posted via the blackboard
    parameter's post_observation for human review.

    In write mode (write=True): full ceremony - apply + git commit.

    One Crate per file - all violations in a file are fixed in a single
    LLM invocation to preserve coherence and minimise API cost.

    Args:
        core_context: Initialized CoreContext.
        target_rule: Only process findings for this rule ID.
        write: If False, dry-run mode - no src/ writes, no commits.
        blackboard: Where to post and mark outcomes (ADR-153 D2) — the
            caller's own identity (WorkerRemediationBlackboard) or a
            declared no-op (NullRemediationBlackboard).
    """

    def __init__(
        self,
        core_context: Any,
        target_rule: str | None,
        write: bool,
        blackboard: RemediationBlackboard,
    ) -> None:
        self._ctx = core_context
        self._target_rule = target_rule
        self._write = write
        self._blackboard = blackboard
        self._interpretation_service = RemediationInterpretationService()

    # -------------------------------------------------------------------------
    # Top-level per-file orchestration
    # -------------------------------------------------------------------------

    # ID: 4ba0914a-f544-4f55-af37-13097abd0ec8
    async def process_file(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
    ) -> bool:
        """
        Public entry point for per-file ceremony.

        Called by the caller (ViolationExecutorWorker, or
        ViolationRemediator's own run() loop) after it has already
        claimed findings and, where applicable, performed the
        RemediationMap gate check.
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
                "RemediationCeremony: cannot read %s - %s",
                file_path,
                exc,
            )
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                f"Cannot read file: {exc}",
            )
            return None

        try:
            baseline_sha = self._ctx.git_service.get_current_commit()
        except RuntimeError as exc:
            logger.warning(
                "RemediationCeremony: git checkpoint failed - %s",
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
                "RemediationCeremony: architectural context failed for %s - %s "
                "[indeterminate — halting]",
                file_path,
                exc,
            )
            await self._blackboard.mark_findings(findings, "indeterminate")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                f"Architectural context indeterminate: {exc}",
            )
            return None

        role_confidence = (
            architectural_context.get("file_role", {}).get("confidence", 0.0) or 0.0
        )
        if self._write and role_confidence < _CFG.min_role_confidence:
            logger.warning(
                "RemediationCeremony: role confidence %.2f < %.2f for %s "
                "[indeterminate in write mode — halting]",
                role_confidence,
                _CFG.min_role_confidence,
                file_path,
            )
            await self._blackboard.mark_findings(findings, "indeterminate")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                (
                    f"Role confidence {role_confidence:.2f} below write threshold "
                    f"{_CFG.min_role_confidence}. Human review required."
                ),
            )
            return None

        logger.info(
            "RemediationCeremony: plan ready for %s "
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

    def _collect_rule_ids(self, findings: list[dict[str, Any]]) -> list[str] | None:
        """Deduplicated, stably sorted rule ids from *findings*' payloads.

        Returns None if any finding has no resolvable rule id. Such a
        finding must never contribute a fabricated ``"unknown"`` entry to
        the set validated by ``assisted.validate_diff`` — that fallback is
        safe only when building a human-readable label (as
        ``ViolationExecutorWorker._process_file`` and file-mode's
        ``remediate.py`` already do for logging/commit-message purposes),
        never as a member of the actual validated rule set (ADR-154 D1).
        """
        rule_ids: set[str] = set()
        for finding in findings:
            rule = (finding.get("payload") or {}).get("rule")
            if not rule:
                return None
            rule_ids.add(str(rule))
        return sorted(rule_ids)

    def _build_violations_summary(self, findings: list[dict[str, Any]]) -> str:
        """Produce a JSON summary of violations for the LLM prompt."""
        violations = []
        for finding in findings:
            payload = finding.get("payload") or {}
            violations.append(
                {
                    "rule": payload.get("rule", self._target_rule),
                    "file_path": payload.get("file_path"),
                    "line_number": payload.get("line_number"),
                    "message": payload.get("message", ""),
                    "severity": payload.get("severity", "warning"),
                }
            )
        return json.dumps(violations, indent=2)

    def _check_atomic_action_coverage(
        self, findings: list[dict[str, Any]]
    ) -> str | None:
        """Check if all finding rules map to an ACTIVE atomic action.

        Returns the action_id if every rule in *findings* maps to the same
        ACTIVE action with confidence >= 0.80. Returns None otherwise
        (mixed actions, unmapped rules, or low confidence).
        """
        from body.autonomy.audit_analyzer import _load_remediation_map
        from shared.path_resolver import PathResolver

        try:
            path_resolver = PathResolver(self._ctx.git_service.repo_path)
            remediation_map = _load_remediation_map(path_resolver)
        except Exception:
            return None

        if not remediation_map:
            return None

        mapped_actions: set[str] = set()
        for finding in findings:
            payload = finding.get("payload") or {}
            rule = payload.get("rule") or payload.get("check_id") or ""
            entry = remediation_map.get(rule)
            if (
                entry
                and entry.get("status") == "ACTIVE"
                and (entry.get("confidence") or 0) >= 0.80
            ):
                mapped_actions.add(entry["action"])
            else:
                return None

        # Only defer if all findings map to a single atomic action.
        if len(mapped_actions) == 1:
            return mapped_actions.pop()
        return None

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
        # remediation map, this ceremony must not handle them — they
        # belong to the constitutional path (RemediatorWorker). Release
        # the claims back to open so RemediatorWorker can pick them up.
        mapped_action = self._check_atomic_action_coverage(findings)
        if mapped_action is not None:
            logger.info(
                "RemediationCeremony: all rules for %s are covered by atomic "
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
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path, findings, self._target_rule, self._write, "LLM fix failed"
            )
            return False

        crate_id = await self._pack_crate(file_path, proposed_fix)
        if crate_id is None:
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                "Crate creation failed",
            )
            return False

        await self._align_staged_file(crate_id, file_path)

        canary_passed = await self._run_canary(crate_id)
        if not canary_passed:
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                f"Canary failed for crate {crate_id}",
            )
            return False

        # ADR-154 D1: patch generation + assisted.validate_diff safety gate.
        # Fail-closed — once this gate is invoked, a failed verdict must
        # never fall through into the legacy apply/commit branches below,
        # in either dry-run or write mode. A gate whose failure can be
        # silently bypassed is worse than no gate: it manufactures the
        # appearance of a check without its substance.
        rule_ids = self._collect_rule_ids(findings)
        if rule_ids is None:
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                "One or more findings have no resolvable rule id; cannot validate.",
            )
            return False

        patch = await self._generate_patch(file_path, crate_id, plan.baseline_sha)
        if not patch:
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                "Empty or unavailable candidate diff — nothing to validate.",
            )
            return False

        # D2's build_validated_candidate never trusts an in-memory
        # ActionResult — it re-reads a completed assisted.validate_diff row
        # from core.fix_runs by validation_run_id. A raw
        # action_executor.execute() call here would produce only that
        # in-memory result with no durable row for D3 to later construct a
        # candidate from, so this goes through the Body-owned persisted
        # service instead (submit_and_persist_fix — the same INSERT/UPDATE
        # shape the /fix/run API path writes, so a passing row here is
        # indistinguishable to build_validated_candidate from one produced
        # externally by the assisted lane).
        validation_run_id, validate_result = await submit_and_persist_fix(
            context=self._ctx,
            fix_id="assisted.validate_diff",
            write=True,
            params={
                "patch": patch,
                "finding_rules": rule_ids,
                "subject_files": [file_path],
                "base_sha": plan.baseline_sha,
            },
        )
        if not validate_result.ok:
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                "assisted.validate_diff failed "
                f"(validation_run_id={validation_run_id}): "
                f"{validate_result.data.get('error', 'validation did not pass')}",
            )
            return False

        # ADR-154 D3/D5: canonical worker/rule-mode findings get an
        # automatic human-gated DRAFT proposal here, regardless of
        # self._write — proposal creation is not production mutation, so
        # it must not depend on the legacy write flag. Once a DRAFT is
        # created (or its creation fails), this method returns without
        # ever reaching the legacy dry-run/write branches — a canonical
        # passing ceremony must never reach direct apply/commit again.
        worker_uuid = self._blackboard.worker_uuid
        if worker_uuid is not None:
            return await self._create_ceremony_draft(
                file_path,
                findings,
                plan,
                rule_ids,
                patch,
                validation_run_id,
                worker_uuid,
            )

        # ADR-154 D3a (governor correction, 2026-08-23): worker_uuid is
        # None only for CLI file-mode's NullRemediationBlackboard —
        # synthetic, non-canonical findings with no durable blackboard
        # lineage. The settled D3a decision is candidate-export-only:
        # file-mode may not create a proposal (D5's eligibility guard
        # already forecloses that) AND may not reach direct apply/commit
        # either, regardless of self._write. An earlier version of this
        # method fell through to the legacy dry-run/write branches here,
        # which meant `--file ... --write` still applied and committed
        # directly — exactly the authority D3a exists to remove. That
        # legacy code is relocated to _legacy_dry_run_and_write below
        # (kept defined, physically present, for D4 to delete
        # structurally) — no caller reaches it anymore.
        return await self._export_candidate_only(
            file_path, findings, plan, rule_ids, patch, validation_run_id
        )

    async def _legacy_dry_run_and_write(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        plan: _RemediationPlan,
        crate_id: str,
        canary_passed: bool,
        proposed_fix: str,
    ) -> bool:
        """Dead code as of ADR-154 D3 — no caller reaches this anymore.

        Every _execute_file path now returns before this method could be
        called: worker-backed ceremonies via _create_ceremony_draft,
        file-mode via _export_candidate_only (ADR-154 D3a,
        candidate-export-only). Preserved verbatim rather than deleted —
        D4 owns removing this method, the CLI --write flag, and the
        worker-declaration crate.apply/git.commit authority together, per
        ADR-154's own text ("remove write from RemediationCeremony...
        delete the write behavioural branch, apply_and_finalize_crate, and
        the direct commit_paths call"). Left here so D4 is a deletion, not
        a rewrite.
        """
        if not self._write:
            await self._blackboard.post_observation(
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
                status="dry_run_complete",
            )
            # Source findings are marked 'abandoned', not 'dry_run_complete':
            # the dry-run candidate report (posted above) carries all the fix
            # information; the source findings represent a violation that was
            # NOT fixed, so sensors must be free to re-detect on the next
            # cycle. Per #265 (and aligned with #263 — abandoned is the
            # re-emittable terminal status).
            await self._blackboard.mark_findings(findings, "abandoned")
            logger.info(
                "RemediationCeremony: [DRY-RUN] %s - canary passed, fix ready.",
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
                "RemediationCeremony: apply_and_finalize failed for %s - %s",
                crate_id,
                exc,
            )
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                f"Apply failed: {exc}",
            )
            return False

        # Commit MUST succeed before findings are marked resolved.
        # A failed commit means the repo and the blackboard would disagree
        # about whether the fix is live. That is a data integrity failure.
        # Scope the commit to this file only — autonomous workers must
        # use commit_paths() so unrelated working-tree changes are never
        # swept into a worker's commit.
        try:
            self._ctx.git_service.commit_paths(
                [file_path],
                f"fix({self._target_rule}): autonomous remediation in {file_path}",
            )
        except RuntimeError as exc:
            logger.error(
                "RemediationCeremony: git commit FAILED for %s - %s "
                "[marking abandoned — fix is applied but uncommitted]",
                file_path,
                exc,
            )
            await self._blackboard.mark_findings(findings, "abandoned")
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                f"Git commit failed after apply: {exc}. "
                "Fix is applied to disk but NOT committed. Manual intervention required.",
            )
            return False

        await self._blackboard.post_report(
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
        await self._blackboard.mark_findings(findings, "resolved")

        logger.info(
            "RemediationCeremony: [WRITE] applied %s (crate=%s, rule=%s)",
            file_path,
            crate_id,
            self._target_rule,
        )
        return True

    # -------------------------------------------------------------------------
    # ADR-154 D3 — candidate -> privileged candidate -> human-gated DRAFT
    # -------------------------------------------------------------------------

    async def _create_ceremony_draft(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        plan: _RemediationPlan,
        rule_ids: list[str],
        patch: str,
        validation_run_id: str,
        worker_uuid: uuid.UUID,
    ) -> bool:
        """Build the privileged candidate and atomically submit the
        ceremony's human-gated DRAFT proposal (ADR-154 D3).

        Called only when ``self._blackboard.worker_uuid`` is not None —
        i.e. never for CLI file-mode (ADR-154 D3a stays candidate-export-
        only). ``findings`` are the real canonical blackboard rows this
        ceremony claimed; their ``id``s are the candidate's finding_ids.

        On any failure (candidate construction, or the atomic submission),
        deliberately does NOT touch finding claim/status. The submission
        service's transaction is all-or-nothing — a failed submission
        changes nothing in the database, so the findings remain exactly as
        claimed (normally still owned by this worker). Calling
        ``release_claimed_entries`` here would be unsafe (it checks
        ``status='claimed'`` only, not ownership — CLAUDE.md/#812-adjacent
        concern) and is unnecessary: nothing needs releasing when nothing
        changed. A submission that failed specifically because
        ``claimed_by`` no longer matches this worker means some other
        worker now legitimately owns that row — this method must not mark
        it abandoned or anything else, since it is no longer this
        ceremony's claim to dispose of. Any row that stayed stuck this way
        is within the periodic orphan-claim reaper's existing remit
        (ADR-072), not a new gap this method must plug.
        """
        canonical_finding_ids = [str(f["id"]) for f in findings]

        try:
            candidate = await build_validated_candidate(
                finding_ids=canonical_finding_ids,
                rule_ids=rule_ids,
                patch=patch,
                validation_run_id=validation_run_id,
                subject_files=[file_path],
            )
        except CandidateConstructionError as exc:
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                f"Candidate construction failed: {exc}",
            )
            return False

        proposal = build_assisted_lane_draft_proposal(
            candidate,
            goal=(
                f"Autonomous remediation of {', '.join(rule_ids)} in "
                f"{file_path} via ceremony-authored diff"
            ),
            created_by="remediation-ceremony",
            extra_constraints={"proposal_origin": "ceremony"},
        )
        proposal_model = ProposalMapper.to_db_model(proposal, AutonomousProposal)

        try:
            proposal_id = await submit_ceremony_proposal(
                proposal_model,
                finding_ids=canonical_finding_ids,
                expected_worker_uuid=worker_uuid,
                expected_rule_ids=rule_ids,
            )
        except ProposalSubmissionError as exc:
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                f"Ceremony proposal submission failed: {exc}",
            )
            return False

        # The atomic submission already transitioned every finding
        # claimed -> deferred_to_proposal in SQL — no mark_findings call
        # here would be correct (the legacy 'abandoned'/'resolved' terminal
        # statuses do not apply to a deferred finding).
        await self._blackboard.post_report(
            subject=f"{_DRAFT_SUBJECT}::{file_path}",
            payload={
                "file_path": file_path,
                "proposal_id": proposal_id,
                "candidate_id": candidate.candidate_id,
                "rule_ids": rule_ids,
                "finding_ids": canonical_finding_ids,
                "validation_run_id": validation_run_id,
                "production_set": candidate.production_set,
                "baseline_sha": plan.baseline_sha,
            },
        )
        logger.info(
            "RemediationCeremony: [DRAFT] created proposal %s for %s "
            "(%d finding(s), rules=%s)",
            proposal_id,
            file_path,
            len(findings),
            rule_ids,
        )
        return True

    async def _export_candidate_only(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        plan: _RemediationPlan,
        rule_ids: list[str],
        patch: str,
        validation_run_id: str,
    ) -> bool:
        """ADR-154 D3a candidate-export-only terminus.

        Called only when ``self._blackboard.worker_uuid`` is None — i.e.
        only for CLI file-mode's ``NullRemediationBlackboard``, whose
        findings are synthetic UUIDs with no durable blackboard lineage.
        Builds the privileged ``ValidatedRemediationCandidate`` purely for
        inspection: never constructs or submits a proposal (the candidate's
        ``finding_ids`` here are file-mode's synthetic UUIDs — diagnostic
        metadata only, never real lineage a submission could defer), and
        never reaches ``apply_and_finalize_crate``/``commit_paths``
        regardless of ``self._write``. This is the fix for a real D3
        defect the governor caught: without this terminus, worker_uuid
        being None simply fell through to ``_legacy_dry_run_and_write``,
        so ``--file ... --write`` still applied and committed directly —
        exactly the authority D3a's candidate-export-only decision exists
        to remove.

        ``NullRemediationBlackboard``'s methods are true no-ops (ADR-153),
        so this posts nothing anywhere — matching the pre-D3 file-mode
        dry-run terminus, which also posted nothing for the same reason.
        The candidate's fields (patch, patch_digest, validated_base_sha,
        production_set) are still constructed and logged for local
        operator visibility even though nothing durable is written.
        """
        try:
            candidate = await build_validated_candidate(
                finding_ids=[str(f["id"]) for f in findings],
                rule_ids=rule_ids,
                patch=patch,
                validation_run_id=validation_run_id,
                subject_files=[file_path],
            )
        except CandidateConstructionError as exc:
            await self._blackboard.post_failed(
                file_path,
                findings,
                self._target_rule,
                self._write,
                f"Candidate construction failed: {exc}",
            )
            return False

        await self._blackboard.post_observation(
            subject=f"{_DRY_RUN_SUBJECT}::{file_path}",
            payload={
                "file_path": file_path,
                "rule": self._target_rule,
                "candidate_id": candidate.candidate_id,
                "patch": candidate.patch,
                "patch_digest": candidate.patch_digest,
                "validated_base_sha": candidate.validated_base_sha,
                "production_set": candidate.production_set,
                "validation_run_id": validation_run_id,
                "rule_ids": rule_ids,
                "violations_count": len(findings),
                "architectural_context": plan.architectural_context,
                "message": (
                    "Candidate-export-only (ADR-154 D3a): CLI file-mode "
                    "findings are synthetic and have no canonical "
                    "blackboard lineage, so this candidate cannot back a "
                    "proposal. Nothing was written or committed. Submit "
                    "through a canonical worker/rule-mode ceremony, or the "
                    "assisted lane, if this fix should be applied."
                ),
            },
            status="dry_run_complete",
        )
        await self._blackboard.mark_findings(findings, "abandoned")
        logger.info(
            "RemediationCeremony: [CANDIDATE-EXPORT] %s - assisted.validate_diff "
            "passed, candidate %s ready for inspection (no proposal, no write, "
            "no commit).",
            file_path,
            candidate.candidate_id,
        )
        return True
