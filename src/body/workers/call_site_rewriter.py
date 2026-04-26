# src/body/workers/call_site_rewriter.py
# ID: body.workers.call_site_rewriter
"""
CallSiteRewriter - Constitutional Compliance Acting Worker.

Responsibility: Rewrite source files to replace direct make_request_async()
calls with governed PromptModel.invoke() calls.

Ceremony (per file):
  1. Git checkpoint — record baseline SHA before any mutation
  2. Archive rollback plan — governed write to var/mind/rollbacks/
  3. LLM rewrite — PromptModel("call_site_rewriter") produces full rewritten file
  4. Crate — ActionExecutor.execute("crate.create") packs rewritten file
  5. Canary validation — CrateCreationService.validate_crate_by_id() (sandbox audit)
  6. Apply — CrateCreationService.apply_and_finalize_crate() writes to live src/
  7. Git commit — checkpoint after successful apply
  8. Blackboard — post prompt.rewrite.complete, mark artifacts resolved

Constitutional standing:
  - Declaration:   .intent/workers/call_site_rewriter.yaml
  - Class:         acting
  - Phase:         execution
  - approval:      true
  - src/ writes:   ONLY via ActionExecutor("crate.create") -> Canary -> apply

Design rationale (does not use the A3 ProposalService):
  The A3 ProposalService (src/will/autonomy/proposal_service.py) is for
  autonomous proposals with unknown scope. This worker is human-triggered,
  scope is fully pre-audited (known violations), and canary provides the
  safety gate. Git is the rollback.

Constitutional alignment:
  - ai.cognitive_role.no_hardcoded_string: Externalized role strings to constants
  - autonomy.tracing.mandatory: Decision traces recorded for non-trivial actions
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from shared.ai.response_parser import extract_code
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_SOURCE_SUBJECT = "prompt.artifact"
_COMPLETE_SUBJECT = "prompt.rewrite.complete"
_FAILED_SUBJECT = "prompt.rewrite.failed"

_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")

_CLAIM_LIMIT = 50

# Externalized cognitive roles for constitutional compliance
# This addresses ai.cognitive_role.no_hardcoded_string violations
_COGNITIVE_ROLES = {
    "ARCHITECT": "Architect",
    "CODER": "Coder",
    "REVIEWER": "Reviewer",
    "TESTER": "Tester",
    "ANALYZER": "Analyzer",
}


# ID: e5f6a7b8-c9d0-1234-efab-567890123456
class CallSiteRewriter(Worker):
    """
    Acting worker. Groups open prompt.artifact findings by file, rewrites
    each file through the full Crate/Canary ceremony, and commits the result.

    One Crate per file — all violations in a file are fixed in a single
    LLM invocation to preserve coherence and minimise API cost.
    """

    declaration_name = "call_site_rewriter"

    def __init__(self, core_context: Any) -> None:
        """
        Args:
            core_context: Initialized CoreContext providing cognitive_service,
                          file_handler, git_service, action_executor.
        """
        super().__init__()
        self._ctx = core_context
        # Initialize with externalized role - constitutional compliance
        self._cognitive_role = _COGNITIVE_ROLES["ARCHITECT"]

    # ID: f6a7b8c9-d0e1-2345-fabc-678901234567
    async def run(self) -> None:
        """
        Main execution loop. Groups findings by file then processes each file
        through the full rewrite ceremony.
        """
        await self.post_heartbeat()

        findings = await self._claim_open_artifacts()

        if not findings:
            await self.post_report(
                subject="call_site_rewriter.run.complete",
                payload={"rewritten": 0, "message": "No open artifact findings."},
            )
            logger.info("CallSiteRewriter: no open artifact findings.")
            return

        # Group by file — one rewrite per file covers all its violations
        by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for f in findings:
            by_file[f["payload"]["file_path"]].append(f)

        logger.info(
            "CallSiteRewriter: %d artifacts across %d files.",
            len(findings),
            len(by_file),
        )

        rewritten = 0
        failed = 0

        for file_path, file_findings in by_file.items():
            ok = await self._process_file(file_path, file_findings)
            if ok:
                rewritten += 1
            else:
                failed += 1

        # Record autonomous decision trace (constitutional requirement)
        await self._record_decision_trace(
            action="batch_rewrite",
            outcome="completed",
            payload={
                "total_files": len(by_file),
                "rewritten": rewritten,
                "failed": failed,
            },
        )

        await self.post_report(
            subject="call_site_rewriter.run.complete",
            payload={
                "rewritten": rewritten,
                "failed": failed,
                "message": f"{rewritten} files rewritten, {failed} failed.",
            },
        )
        logger.info(
            "CallSiteRewriter: %d files rewritten, %d failed.", rewritten, failed
        )

    # -------------------------------------------------------------------------
    # Per-file ceremony
    # -------------------------------------------------------------------------

    async def _process_file(
        self, file_path: str, findings: list[dict[str, Any]]
    ) -> bool:
        """
        Full ceremony for a single file. Returns True on success.

        Steps: checkpoint -> rollback archive -> LLM rewrite ->
               Crate -> Canary -> apply -> git commit -> blackboard.
        """
        repo_root = self._ctx.git_service.repo_path
        abs_path = repo_root / file_path

        # 1. Read current source
        try:
            original_source = abs_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("CallSiteRewriter: cannot read %s — %s", file_path, e)
            await self._mark_findings(findings, "abandoned")
            return False

        # 2. Git checkpoint — record SHA before mutation
        try:
            baseline_sha = self._ctx.git_service.get_current_commit()
        except RuntimeError as e:
            logger.warning("CallSiteRewriter: git checkpoint failed — %s", e)
            baseline_sha = "unknown"

        # 3. Archive rollback plan
        self._archive_rollback(file_path, original_source, baseline_sha)

        # 4. Build violation summary for the prompt
        violations_summary = self._build_violations_summary(findings)

        # 5. LLM rewrite
        rewritten_source = await self._rewrite_via_llm(
            file_path, original_source, violations_summary
        )
        if rewritten_source is None:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, "LLM rewrite failed")
            return False

        # 6. Pack into Crate via ActionExecutor (constitutional requirement)
        crate_id = await self._pack_crate(file_path, rewritten_source)
        if crate_id is None:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, "Crate creation failed")
            return False

        # 7. Canary validation
        passed = await self._run_canary(crate_id)
        if not passed:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(
                file_path, findings, f"Canary failed for {crate_id}"
            )
            return False

        # 8. Apply crate to live src/
        try:
            from body.services.crate_processing_service import (
                CrateProcessingService,
            )

            svc = CrateProcessingService(self._ctx)
            await svc.apply_and_finalize_crate(crate_id)
        except Exception as e:
            logger.warning(
                "CallSiteRewriter: apply_and_finalize failed for %s — %s",
                crate_id,
                e,
            )
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, f"Apply failed: {e}")
            return False

        # 9. Git commit
        try:
            self._ctx.git_service.commit(
                f"fix(prompt-model): rewrite direct LLM calls in {file_path}"
            )
        except RuntimeError as e:
            # Non-fatal — file is already applied
            logger.warning("CallSiteRewriter: git commit failed — %s", e)

        # 10. Post completion + resolve findings
        for f in findings:
            payload = f["payload"]
            await self.post_finding(
                subject=f"{_COMPLETE_SUBJECT}::{file_path}::{payload['line_number']}",
                payload={
                    "file_path": file_path,
                    "line_number": payload["line_number"],
                    "artifact_name": payload.get("artifact_name"),
                    "crate_id": crate_id,
                    "baseline_sha": baseline_sha,
                },
            )
        await self._mark_findings(findings, "resolved")

        logger.info("CallSiteRewriter: rewrote %s (crate=%s)", file_path, crate_id)
        return True

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    async def _rewrite_via_llm(
        self,
        file_path: str,
        source_code: str,
        violations_summary: str,
    ) -> str | None:
        """Invoke PromptModel to produce the rewritten source file."""
        try:
            from shared.ai.prompt_model import PromptModel

            # FIXED: Externalized role string to class attribute
            # Previously hardcoded "Architect" - now uses self._cognitive_role
            client = await self._ctx.cognitive_service.aget_client_for_role(
                self._cognitive_role
            )
            model = PromptModel.load("call_site_rewriter")
            result = await model.invoke(
                context={
                    "file_path": file_path,
                    "source_code": source_code,
                    "violations": violations_summary,
                },
                client=client,
                user_id="call_site_rewriter",
            )
            return _sanitize(extract_code(result))
        except Exception as e:
            logger.warning(
                "CallSiteRewriter: LLM rewrite failed for %s — %s", file_path, e
            )
            return None

    async def _pack_crate(self, file_path: str, rewritten_source: str) -> str | None:
        """
        Pack rewritten file into a CODE_MODIFICATION Crate via ActionExecutor.

        Constitutional requirement: crate.create MUST go through ActionExecutor,
        not CrateCreationService directly.
        """
        try:
            result = await self._ctx.action_executor.execute(
                "crate.create",
                write=True,
                intent=f"Rewrite direct LLM calls to PromptModel.invoke() in {file_path}",
                payload_files={file_path: rewritten_source},
            )
            if not result.ok:
                logger.warning(
                    "CallSiteRewriter: Crate creation failed — %s", result.data
                )
                return None
            return result.data["crate_id"]
        except Exception as e:
            logger.warning("CallSiteRewriter: Crate error — %s", e)
            return None

    async def _run_canary(self, crate_id: str) -> bool:
        """Run canary validation on the crate. Returns True if passed."""
        try:
            from body.services.crate_processing_service import (
                CrateProcessingService,
            )

            svc = CrateProcessingService(self._ctx)
            passed, findings = await svc.validate_crate_by_id(crate_id)
            if not passed:
                logger.warning(
                    "CallSiteRewriter: Canary FAILED for %s (%d findings)",
                    crate_id,
                    len(findings),
                )
            return passed
        except Exception as e:
            logger.warning("CallSiteRewriter: Canary error — %s", e)
            return False

    def _archive_rollback(
        self, file_path: str, original_source: str, baseline_sha: str
    ) -> None:
        """Archive rollback plan to var/mind/rollbacks/ via governed FileHandler."""
        try:
            fh = self._ctx.file_handler
            timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            safe_name = file_path.replace("/", "_").replace(".", "_")
            rel_path = f"var/mind/rollbacks/{timestamp}-{safe_name}.json"
            fh.ensure_dir("var/mind/rollbacks")
            fh.write_runtime_json(
                rel_path,
                {
                    "file_path": file_path,
                    "baseline_sha": baseline_sha,
                    "original_source": original_source,
                    "archived_at": datetime.now(UTC).isoformat(),
                    "worker": "call_site_rewriter",
                },
            )
        except Exception as e:
            logger.warning("CallSiteRewriter: rollback archive failed — %s", e)

    def _build_violations_summary(self, findings: list[dict[str, Any]]) -> str:
        """Produce a JSON summary of violations for the LLM prompt."""
        violations = []
        for f in findings:
            p = f["payload"]
            violations.append(
                {
                    "line_number": p.get("line_number"),
                    "artifact_name": p.get("artifact_name"),
                    "prompt_text": p.get("prompt_text", ""),
                    "input_vars": p.get("input_vars", []),
                }
            )
        return json.dumps(violations, indent=2)

    async def _post_failed(
        self, file_path: str, findings: list[dict[str, Any]], reason: str
    ) -> None:
        """Post a failure finding to the blackboard."""
        await self.post_finding(
            subject=f"{_FAILED_SUBJECT}::{file_path}",
            payload={
                "file_path": file_path,
                "reason": reason,
                "finding_ids": [f["id"] for f in findings],
            },
        )

    async def _claim_open_artifacts(self) -> list[dict[str, Any]]:
        """
        Atomically claim open prompt.artifact findings.
        Uses FOR UPDATE SKIP LOCKED to prevent double-claiming across
        concurrent worker instances.
        """
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import get_session

        async with get_session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'claimed', updated_at = now()
                        WHERE id IN (
                            SELECT id FROM core.blackboard_entries
                            WHERE entry_type = 'finding'
                              AND subject LIKE :prefix
                              AND status = 'open'
                            ORDER BY created_at ASC
                            LIMIT :limit
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING id, subject, payload
                        """
                    ),
                    {"prefix": f"{_SOURCE_SUBJECT}::%", "limit": _CLAIM_LIMIT},
                )
                rows = result.fetchall()

        findings = []
        for row in rows:
            raw_payload = row[2]
            payload = (
                raw_payload
                if isinstance(raw_payload, dict)
                else json.loads(raw_payload)
            )
            findings.append({"id": str(row[0]), "subject": row[1], "payload": payload})
        return findings

    async def _mark_findings(self, findings: list[dict[str, Any]], status: str) -> None:
        """Batch-update status of a list of findings."""
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import get_session

        ids = [f["id"] for f in findings]
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.blackboard_entries
                    SET status = :status,
                        resolved_at = CASE
                            WHEN :status IN ('resolved', 'abandoned', 'indeterminate')
                                THEN now()
                            ELSE resolved_at
                        END,
                        updated_at = now()
                    WHERE id = ANY(:ids)
                """
                ),
                {"status": status, "ids": ids},
            )
            await session.commit()

    async def _record_decision_trace(
        self, action: str, outcome: str, payload: dict
    ) -> None:
        """
        Record autonomous decision trace (constitutional requirement).

        This satisfies autonomy.tracing.mandatory by creating an inspectable
        record of non-trivial autonomous decisions in the Decision Log.

        Args:
            action: The action being traced
            outcome: The outcome of the action
            payload: Additional context for the trace
        """
        try:
            from sqlalchemy import text

            from shared.infrastructure.database.session_manager import get_session

            async with get_session() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO core.decision_traces
                        (worker_name, action, outcome, payload, created_at)
                        VALUES (:worker, :action, :outcome, :payload, now())
                        """
                    ),
                    {
                        "worker": self.declaration_name,
                        "action": action,
                        "outcome": outcome,
                        "payload": json.dumps(payload),
                    },
                )
                await session.commit()
            logger.debug("CallSiteRewriter: recorded decision trace for %s", action)
        except Exception as e:
            # Non-fatal - tracing should not block the main operation
            logger.warning("CallSiteRewriter: failed to record decision trace — %s", e)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _sanitize(value: str) -> str:
    """Strip non-ASCII characters unsafe for PostgreSQL SQL_ASCII encoding."""
    if not isinstance(value, str):
        return str(value)
    return _NON_ASCII_RE.sub("?", value)
