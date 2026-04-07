# src/body/workers/violation_remediator.py
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

import asyncio
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.self_healing.remediation_interpretation.service import (
    RemediationInterpretationError,
    RemediationInterpretationService,
)
from shared.workers.base import Worker


logger = getLogger(__name__)

_SOURCE_SUBJECT = "audit.violation"
_COMPLETE_SUBJECT = "audit.remediation.complete"
_DRY_RUN_SUBJECT = "audit.remediation.dry_run"
_FAILED_SUBJECT = "audit.remediation.failed"


_CLAIM_LIMIT = 50

_CODE_COLLECTION = "core-code"
_SEMANTIC_EXAMPLES_LIMIT = 3

# Minimum role detection confidence required to proceed in write mode.
# Below this threshold the architectural context is too uncertain to trust
# for autonomous code modification.
_MIN_ROLE_CONFIDENCE_FOR_WRITE = 0.55

# Severity ordering for claim priority (higher = claimed first).
_SEVERITY_RANK = {"critical": 4, "error": 3, "warning": 2, "info": 1}


@dataclass
class _RemediationPlan:
    """
    Output of the RUNTIME planning phase.

    This is evidence assembled before the execution ceremony begins.
    It is passed to the LLM as architectural context — not as authority.
    The LLM must treat it as advisory input, not as a directive.
    """

    file_path: str
    original_source: str
    baseline_sha: str
    violations_summary: str
    # architectural_context carries the deterministic brief as evidence.
    # It is NOT a planning authority. It is evidence of the file's
    # detected role, responsibility clusters, and candidate strategies.
    # The LLM is free to disagree with it; it must satisfy the rule.
    architectural_context: dict[str, Any]
    context_text: str


# ID: bb52f62a-45c9-47a4-9ff8-788b0c6ca4f1
class ViolationRemediator(Worker):
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

    declaration_name = "violation_executor"

    def __init__(
        self,
        core_context: Any,
        target_rule: str,
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
            # Planning marked findings already; do not proceed.
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

        # Build architectural context.
        # Failure here is indeterminate — we cannot safely plan without it.
        # We do NOT fall back to an empty brief and continue.
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

        # Confidence gate for write mode.
        # In dry-run mode we allow low-confidence for human review.
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
        # remediation map, defer to the Will-layer proposal pipeline instead
        # of running the generic LLM fixer.
        mapped_action = self._check_atomic_action_coverage(findings)
        if mapped_action is not None:
            logger.info(
                "ViolationRemediator: all rules for %s are covered by atomic "
                "action '%s' — deferring to proposal pipeline",
                file_path,
                mapped_action,
            )
            await self._mark_findings(findings, "deferred_to_proposal")
            await self.post_finding(
                subject=f"{_FAILED_SUBJECT}::{file_path}",
                payload={
                    "file_path": file_path,
                    "rule": self._target_rule,
                    "reason": (
                        f"Deferred to proposal pipeline: atomic action "
                        f"'{mapped_action}' handles these rules. Use "
                        f"'core-admin proposals list' to track execution."
                    ),
                    "write": self._write,
                    "finding_ids": [f["id"] for f in findings],
                    "mapped_action": mapped_action,
                },
            )
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

    # -------------------------------------------------------------------------
    # LLM invocation
    # -------------------------------------------------------------------------

    async def _invoke_llm(
        self,
        file_path: str,
        source_code: str,
        context_text: str,
        violations_summary: str,
        architectural_context: dict[str, Any],
    ) -> str | None:
        """
        Invoke RemoteCoder (Grok) via PromptModel to produce a fix.

        architectural_context is passed as advisory evidence under the key
        'architectural_context'. The prompt template must treat it as
        context, not as a directive. The LLM's obligation is to satisfy
        the violated rule, not to execute the recommended strategy.
        """
        import ast as _ast

        from shared.ai.response_parser import extract_json

        try:
            from shared.ai.prompt_model import PromptModel

            client = await self._ctx.cognitive_service.aget_client_for_role(
                "RemoteCoder"
            )
            model = PromptModel.load("violation_remediator")
            result = await model.invoke(
                context={
                    "file_path": file_path,
                    "source_code": source_code,
                    "context_package": context_text or "(no additional context)",
                    "violations": violations_summary,
                    # NOTE: architectural_context is advisory evidence only.
                    # It describes detected file role and candidate strategies.
                    # It is NOT a planning directive. The fix must satisfy
                    # the violated rule; the context informs, not commands.
                    "architectural_context": json.dumps(
                        architectural_context, indent=2
                    ),
                    "rule_id": self._target_rule,
                },
                client=client,
                user_id="violation_remediator",
            )

            try:
                parsed = extract_json(result)
            except (json.JSONDecodeError, ValueError) as parse_exc:
                logger.warning(
                    "ViolationRemediator: JSON parse failed for %s - %s\nRaw: %s",
                    file_path,
                    parse_exc,
                    (result or "")[:500],
                )
                return None

            code = parsed.get("code") or ""
            if not code:
                logger.warning(
                    "ViolationRemediator: LLM response missing 'code' field for %s",
                    file_path,
                )
                return None

            try:
                _ast.parse(code)
            except SyntaxError as syn_exc:
                logger.warning(
                    "ViolationRemediator: LLM produced invalid Python for %s - %s\n"
                    "First 200 chars: %s",
                    file_path,
                    syn_exc,
                    code[:200],
                )
                return None

            return code

        except Exception as exc:
            logger.warning(
                "ViolationRemediator: LLM invocation failed for %s - %s",
                file_path,
                exc,
            )
            return None

    # -------------------------------------------------------------------------
    # Crate / Canary ceremony helpers
    # -------------------------------------------------------------------------

    async def _pack_crate(self, file_path: str, fixed_source: str) -> str | None:
        """Pack the fixed file into a CODE_MODIFICATION Crate via ActionExecutor."""
        try:
            result = await self._ctx.action_executor.execute(
                "crate.create",
                write=True,
                intent=(
                    f"Fix {self._target_rule} violations in {file_path} "
                    f"via autonomous remediation"
                ),
                payload_files={file_path: fixed_source},
            )
            if not result.ok:
                logger.warning(
                    "ViolationRemediator: Crate creation failed - %s",
                    result.data,
                )
                return None
            return result.data["crate_id"]
        except Exception as exc:
            logger.warning("ViolationRemediator: Crate error - %s", exc)
            return None

    async def _align_staged_file(self, crate_id: str, file_path: str) -> None:
        """Best-effort formatting alignment on the staged crate file.

        Runs black and ruff isort fix on the staged file so that Canary
        does not trip on trivial style issues.  Failures are logged but
        never raised — Canary will catch anything that remains.
        """
        staged = Path(f"var/workflows/crates/inbox/{crate_id}/{file_path}")
        if not staged.exists():
            logger.warning(
                "ViolationRemediator: staged file not found for alignment - %s",
                staged,
            )
            return

        staged_str = str(staged)

        for label, cmd in (
            ("black", ["poetry", "run", "black", staged_str]),
            (
                "ruff-isort",
                [
                    "poetry",
                    "run",
                    "ruff",
                    "check",
                    "--select",
                    "I",
                    "--fix",
                    staged_str,
                ],
            ),
        ):
            try:
                proc = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True, timeout=30
                )
                if proc.returncode == 0:
                    logger.info(
                        "ViolationRemediator: %s aligned %s",
                        label,
                        file_path,
                    )
                else:
                    logger.warning(
                        "ViolationRemediator: %s returned %d for %s - %s",
                        label,
                        proc.returncode,
                        file_path,
                        (proc.stderr or "")[:300],
                    )
            except Exception as exc:
                logger.warning(
                    "ViolationRemediator: %s failed for %s - %s",
                    label,
                    file_path,
                    exc,
                )

    async def _run_canary(self, crate_id: str) -> bool:
        """Run canary validation on the crate. Returns True if passed."""
        try:
            from body.services.crate_processing_service import CrateProcessingService

            service = CrateProcessingService(self._ctx)
            passed, findings = await service.validate_crate_by_id(crate_id)
            if not passed:
                logger.warning(
                    "ViolationRemediator: Canary FAILED for %s (%d findings)",
                    crate_id,
                    len(findings),
                )
            return passed
        except Exception as exc:
            logger.warning("ViolationRemediator: Canary error - %s", exc)
            return False

    # -------------------------------------------------------------------------
    # Rollback archive
    # -------------------------------------------------------------------------

    def _archive_rollback(
        self,
        file_path: str,
        original_source: str,
        baseline_sha: str,
    ) -> None:
        """Archive rollback plan to var/mind/rollbacks/ via governed FileHandler."""
        try:
            file_handler = self._ctx.file_handler
            timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            safe_name = file_path.replace("/", "_").replace(".", "_")
            rel_path = f"var/mind/rollbacks/{timestamp}-{safe_name}.json"

            file_handler.ensure_dir("var/mind/rollbacks")
            file_handler.write_runtime_json(
                rel_path,
                {
                    "file_path": file_path,
                    "rule": self._target_rule,
                    "baseline_sha": baseline_sha,
                    "original_source": original_source,
                    "archived_at": datetime.now(UTC).isoformat(),
                    "worker": "violation_remediator",
                },
            )
        except Exception as exc:
            logger.warning("ViolationRemediator: rollback archive failed - %s", exc)

    # -------------------------------------------------------------------------
    # Context building
    # -------------------------------------------------------------------------

    async def _build_context(self, file_path: str, violations_summary: str) -> str:
        """
        Build a context package for the violating file combining:
        1. Call graph context (ContextService - structural neighbours)
        2. Semantic examples (Qdrant core-code - similar correct implementations)
        """
        parts: list[str] = []

        try:
            ctx_service = self._ctx.context_service
            call_graph_ctx = await ctx_service.get_context_for_file(file_path)
            if call_graph_ctx:
                parts.append(f"=== Call graph context ===\n{call_graph_ctx}")
        except Exception as exc:
            logger.debug(
                "ViolationRemediator: call graph context unavailable for %s - %s",
                file_path,
                exc,
            )

        try:
            qdrant = self._ctx.vector_store
            hits = await qdrant.search(
                collection=_CODE_COLLECTION,
                query=violations_summary,
                limit=_SEMANTIC_EXAMPLES_LIMIT,
            )
            if hits:
                examples = "\n\n".join(
                    h.payload.get("source", "") for h in hits if h.payload
                )
                parts.append(
                    f"=== Semantic examples (correct implementations) ===\n{examples}"
                )
        except Exception as exc:
            logger.debug(
                "ViolationRemediator: semantic context unavailable for %s - %s",
                file_path,
                exc,
            )

        return "\n\n".join(parts) if parts else ""

    # -------------------------------------------------------------------------
    # Summary helpers
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Blackboard helpers
    # -------------------------------------------------------------------------

    def _check_atomic_action_coverage(
        self, findings: list[dict[str, Any]]
    ) -> str | None:
        """Check if all finding rules map to an ACTIVE atomic action.

        Returns the action_id if every rule in *findings* maps to the same
        ACTIVE action with confidence >= 0.80.  Returns None otherwise
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

    async def _post_failed(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        reason: str,
    ) -> None:
        """Post a failure finding to the blackboard."""
        await self.post_finding(
            subject=f"{_FAILED_SUBJECT}::{file_path}",
            payload={
                "file_path": file_path,
                "rule": self._target_rule,
                "reason": reason,
                "write": self._write,
                "finding_ids": [finding["id"] for finding in findings],
            },
        )

    async def _claim_open_findings(self) -> list[dict[str, Any]]:
        """
        Atomically claim open audit.violation findings for the target rule,
        ordered by severity (critical first) then by creation time.

        Uses FOR UPDATE SKIP LOCKED to prevent double-claiming across
        concurrent worker instances.
        """
        bb = await self._ctx.registry.get_blackboard_service()
        return await bb.claim_violation_findings(
            prefix=f"{_SOURCE_SUBJECT}::%",
            limit=_CLAIM_LIMIT,
            claimed_by=self._worker_uuid,
        )

    async def _mark_findings(self, findings: list[dict[str, Any]], status: str) -> None:
        """Batch-update status of a list of findings."""
        for finding in findings:
            await self._mark_finding(finding["id"], status)

    async def _mark_finding(self, finding_id: str, status: str) -> None:
        """Update the status of a single blackboard finding by ID."""
        bb = await self._ctx.registry.get_blackboard_service()
        await bb.update_entry_status(finding_id, status)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
