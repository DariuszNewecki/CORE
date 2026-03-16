# src/body/workers/violation_remediator.py
# ID: body.workers.violation_remediator
"""
ViolationRemediator - Constitutional Compliance Acting Worker.

Responsibility: For each open audit violation finding on the blackboard,
build a context package for the violating file, invoke RemoteCoder (Grok)
via PromptModel to produce a fix, validate via Crate/Canary ceremony, and
apply to live src/ with a git commit.

Dry-run safety chain:
  - write=False → LLM runs, proposed fix is produced
  - write=False → Crate is created (packed) but NOT applied
  - write=False → Canary runs on the Crate (validates without applying)
  - write=False → No git commit
  - write=False → Blackboard entry posted as status='dry_run_complete'
                  with full proposed fix for human review
  - write=True  → Full ceremony: apply + commit

Constitutional standing:
- Declaration:      .intent/workers/violation_remediator.yaml
- Class:            acting
- Phase:            execution
- Permitted tools:  llm.remote_coder, file.read, crate.create,
                    canary.validate, crate.apply, git.commit
- Approval:         true

LAYER: body/workers — acting worker. Receives CoreContext via constructor
injection. All src/ writes via ActionExecutor -> Crate -> Canary -> apply.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_SOURCE_SUBJECT = "audit.violation"
_COMPLETE_SUBJECT = "audit.remediation.complete"
_DRY_RUN_SUBJECT = "audit.remediation.dry_run"
_FAILED_SUBJECT = "audit.remediation.failed"

_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")

_CLAIM_LIMIT = 50

# Qdrant collection for Python source semantic search
_CODE_COLLECTION = "core-code"

# Number of semantic examples to fetch per violating file
_SEMANTIC_EXAMPLES_LIMIT = 3


# ID: bb52f62a-45c9-47a4-9ff8-788b0c6ca4f1
class ViolationRemediator(Worker):
    """
    Acting worker. Claims open audit violation findings from the blackboard,
    builds context for the violating file, invokes RemoteCoder (Grok) via
    PromptModel to produce a fix, then runs the full Crate/Canary ceremony.

    In dry-run mode (write=False): LLM and Canary run, nothing is applied,
    proposed fix is posted to the blackboard for human review.

    In write mode (write=True): full ceremony — apply + git commit.

    One Crate per file — all violations in a file are fixed in a single
    LLM invocation to preserve coherence and minimise API cost.

    Args:
        core_context: Initialized CoreContext.
        target_rule: Only process findings for this rule ID.
        write: If False, dry-run mode — no src/ writes, no commits.
    """

    declaration_name = "violation_remediator"

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

        # Group by file — one LLM call per file covers all its violations
        by_file: dict[str, list[dict[str, Any]]] = {}
        for f in findings:
            fp = f["payload"]["file_path"]
            by_file.setdefault(fp, []).append(f)

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
                "message": (f"[{mode}] {succeeded} files processed, {failed} failed."),
            },
        )
        logger.info(
            "ViolationRemediator: [%s] %d succeeded, %d failed.",
            mode,
            succeeded,
            failed,
        )

    # -------------------------------------------------------------------------
    # Per-file ceremony
    # -------------------------------------------------------------------------

    async def _process_file(
        self, file_path: str, findings: list[dict[str, Any]]
    ) -> bool:
        """
        Full ceremony (or dry-run) for a single file.
        """
        repo_root = self._ctx.git_service.repo_path
        abs_path = repo_root / file_path

        # 1. Read current source
        try:
            original_source = abs_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("ViolationRemediator: cannot read %s — %s", file_path, e)
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, f"Cannot read file: {e}")
            return False

        # 2. Git checkpoint
        try:
            baseline_sha = self._ctx.git_service.get_current_commit()
        except RuntimeError as e:
            logger.warning("ViolationRemediator: git checkpoint failed — %s", e)
            baseline_sha = "unknown"

        # 3. Rollback archive (write mode only)
        if self._write:
            self._archive_rollback(file_path, original_source, baseline_sha)

        # 4. Build violations summary for the LLM prompt
        violations_summary = self._build_violations_summary(findings)

        # 5. Build context package — call graph context + semantic examples
        context_text = await self._build_context(file_path, violations_summary)

        # 6. LLM fix via PromptModel + RemoteCoder (Grok)
        proposed_fix = await self._invoke_llm(
            file_path, original_source, context_text, violations_summary
        )
        if proposed_fix is None:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, "LLM fix failed")
            return False

        # 7. Pack into Crate via ActionExecutor
        crate_id = await self._pack_crate(file_path, proposed_fix)
        if crate_id is None:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, "Crate creation failed")
            return False

        # 8. Canary validation
        canary_passed = await self._run_canary(crate_id)
        if not canary_passed:
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(
                file_path, findings, f"Canary failed for crate {crate_id}"
            )
            return False

        # ---- DRY-RUN BRANCH ----
        if not self._write:
            await self.post_finding(
                subject=f"{_DRY_RUN_SUBJECT}::{file_path}",
                payload={
                    "file_path": file_path,
                    "rule": self._target_rule,
                    "crate_id": crate_id,
                    "baseline_sha": baseline_sha,
                    "canary_passed": canary_passed,
                    "proposed_fix": proposed_fix,
                    "violations_count": len(findings),
                    "message": (
                        "Dry-run complete. Canary passed. "
                        "Review 'proposed_fix' then re-run with write=True."
                    ),
                },
            )
            await self._mark_findings(findings, "dry_run_complete")
            logger.info(
                "ViolationRemediator: [DRY-RUN] %s — canary passed, fix ready for review.",
                file_path,
            )
            return True

        # ---- WRITE BRANCH ----

        # 9. Apply crate to live src/
        try:
            from body.services.crate_processing_service import CrateProcessingService

            svc = CrateProcessingService(self._ctx)
            await svc.apply_and_finalize_crate(crate_id)
        except Exception as e:
            logger.warning(
                "ViolationRemediator: apply_and_finalize failed for %s — %s",
                crate_id,
                e,
            )
            await self._mark_findings(findings, "abandoned")
            await self._post_failed(file_path, findings, f"Apply failed: {e}")
            return False

        # 10. Git commit
        try:
            self._ctx.git_service.commit(
                f"fix({self._target_rule}): autonomous remediation in {file_path}"
            )
        except RuntimeError as e:
            logger.warning("ViolationRemediator: git commit failed — %s", e)

        # 11. Post completion + resolve findings
        await self.post_finding(
            subject=f"{_COMPLETE_SUBJECT}::{file_path}",
            payload={
                "file_path": file_path,
                "rule": self._target_rule,
                "crate_id": crate_id,
                "baseline_sha": baseline_sha,
                "violations_fixed": len(findings),
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
    # Context building
    # -------------------------------------------------------------------------

    async def _build_context(self, file_path: str, violations_summary: str) -> str:
        """
        Build a context package for the violating file combining:
        1. Call graph context (ContextService — structural neighbours)
        2. Semantic examples (Qdrant core-code — similar correct implementations)

        Returns a formatted string suitable for inclusion in the LLM prompt.
        """
        sections: list[str] = []

        # --- Part 1: Call graph context ---
        call_graph_ctx = await self._build_call_graph_context(file_path)
        if call_graph_ctx:
            sections.append(call_graph_ctx)

        # --- Part 2: Semantic examples from Qdrant ---
        semantic_ctx = await self._build_semantic_context(file_path, violations_summary)
        if semantic_ctx:
            sections.append(semantic_ctx)

        return "\n\n".join(sections)

    async def _build_call_graph_context(self, file_path: str) -> str:
        """Structural context from ContextService (call graph neighbours)."""
        try:
            task_spec = {
                "task_id": f"remediation::{self._target_rule}::{file_path}",
                "summary": (f"Fix {self._target_rule} violations in {file_path}"),
                "task_type": "code_modification",
                "scope": {
                    "include": [file_path],
                    "traversal_depth": 1,
                },
                "constraints": {
                    "max_tokens": 8000,
                    "max_items": 20,
                },
            }
            packet = await self._ctx.context_service.build_for_task(
                task_spec, use_cache=False
            )
            items = packet.get("context", [])
            if not items:
                return ""

            lines = [f"## Structural Context for {file_path}", ""]
            for item in items:
                name = item.get("name", "unknown")
                path = item.get("path", "unknown")
                content = item.get("content", "")
                if content:
                    lines.append(f"### {path}::{name}")
                    lines.append("```python")
                    lines.append(content)
                    lines.append("```")
                    lines.append("")
            return "\n".join(lines)

        except Exception as e:
            logger.warning(
                "ViolationRemediator: call graph context failed for %s — %s",
                file_path,
                e,
            )
            return ""

    async def _build_semantic_context(
        self, file_path: str, violations_summary: str
    ) -> str:
        """
        Semantic context: find similar correct implementations in core-code.

        Query vector is built from the violation description — "find code
        that handles this kind of concern" rather than "find code that looks
        like the violating file." This surfaces relevant examples of correct
        patterns for the LLM to learn from.

        Excludes the violating file itself from results.
        Falls back silently if Qdrant or cognitive service is unavailable.
        """
        try:
            cognitive = self._ctx.cognitive_service
            if cognitive is None:
                return ""

            qdrant = getattr(self._ctx, "qdrant_service", None)
            if qdrant is None:
                return ""

            # Build query from rule + violation context — semantic intent
            query_text = (
                f"rule: {self._target_rule}\n" f"violations:\n{violations_summary}"
            )

            embedding = await cognitive.get_embedding_for_code(query_text)
            if embedding is None:
                return ""

            results = await qdrant.search(
                collection_name=_CODE_COLLECTION,
                query_vector=(
                    list(embedding) if hasattr(embedding, "__iter__") else embedding
                ),
                limit=_SEMANTIC_EXAMPLES_LIMIT + 1,  # +1 to absorb self-match
            )

            if not results:
                return ""

            lines = ["## Semantic Examples — Similar Correct Implementations", ""]
            added = 0

            for hit in results:
                payload = hit.payload or {}
                example_path = payload.get("file_path", "")

                # Skip the violating file itself
                if example_path == file_path:
                    continue

                section = payload.get("section", "unknown")
                score = round(hit.score, 3)

                # Read the actual source chunk text from the Qdrant payload
                # (the text field is not stored — read from disk via file_path)
                chunk_text = await self._read_chunk_from_disk(example_path, payload)
                if not chunk_text:
                    continue

                lines.append(f"### {example_path}::{section} (similarity={score})")
                lines.append("```python")
                lines.append(chunk_text)
                lines.append("```")
                lines.append("")
                added += 1

                if added >= _SEMANTIC_EXAMPLES_LIMIT:
                    break

            if added == 0:
                return ""

            logger.info(
                "ViolationRemediator: added %d semantic examples for %s",
                added,
                file_path,
            )
            return "\n".join(lines)

        except Exception as e:
            logger.warning(
                "ViolationRemediator: semantic context failed for %s — %s",
                file_path,
                e,
            )
            return ""

    async def _read_chunk_from_disk(
        self, file_path: str, payload: dict[str, Any]
    ) -> str:
        """
        Read the relevant chunk text from disk using the chunk metadata.
        Falls back to first 1500 chars of file if chunk boundaries unavailable.
        """
        try:
            repo_root = self._ctx.git_service.repo_path
            abs_path = repo_root / file_path
            if not abs_path.exists():
                return ""

            source = abs_path.read_text(encoding="utf-8", errors="replace")

            # Try to extract just the relevant symbol using section name
            section = payload.get("section", "")
            chunk_type = payload.get("chunk_type", "")

            if (
                chunk_type in ("class", "function")
                and section
                and "_part" not in section
            ):
                import ast

                try:
                    tree = ast.parse(source)
                    lines = source.splitlines()
                    for node in tree.body:
                        if (
                            isinstance(
                                node,
                                (
                                    ast.ClassDef,
                                    ast.FunctionDef,
                                    ast.AsyncFunctionDef,
                                ),
                            )
                            and node.name == section
                        ):
                            start = node.lineno - 1
                            end = node.end_lineno or (start + 50)
                            return "\n".join(lines[start:end])
                except Exception:
                    pass

            # Fallback: first 1500 chars
            return source[:1500]

        except Exception:
            return ""

    # -------------------------------------------------------------------------
    # LLM invocation
    # -------------------------------------------------------------------------

    async def _invoke_llm(
        self,
        file_path: str,
        source_code: str,
        context_text: str,
        violations_summary: str,
    ) -> str | None:
        """
        Invoke PromptModel('violation_remediator') with RemoteCoder (Grok)
        to produce a fixed version of the source file.
        """
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
                    "rule_id": self._target_rule,
                },
                client=client,
                user_id="violation_remediator",
            )
            from shared.ai.response_parser import extract_code

            fixed = _sanitize(extract_code(result))
            if not fixed:
                logger.warning(
                    "ViolationRemediator: LLM returned empty fix for %s", file_path
                )
                return None
            return fixed

        except Exception as e:
            logger.warning(
                "ViolationRemediator: LLM invocation failed for %s — %s",
                file_path,
                e,
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
                    "ViolationRemediator: Crate creation failed — %s", result.data
                )
                return None
            return result.data["crate_id"]
        except Exception as e:
            logger.warning("ViolationRemediator: Crate error — %s", e)
            return None

    async def _run_canary(self, crate_id: str) -> bool:
        """Run canary validation on the crate. Returns True if passed."""
        try:
            from body.services.crate_processing_service import CrateProcessingService

            svc = CrateProcessingService(self._ctx)
            passed, findings = await svc.validate_crate_by_id(crate_id)
            if not passed:
                logger.warning(
                    "ViolationRemediator: Canary FAILED for %s (%d findings)",
                    crate_id,
                    len(findings),
                )
            return passed
        except Exception as e:
            logger.warning("ViolationRemediator: Canary error — %s", e)
            return False

    # -------------------------------------------------------------------------
    # Rollback archive
    # -------------------------------------------------------------------------

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
                    "rule": self._target_rule,
                    "baseline_sha": baseline_sha,
                    "original_source": original_source,
                    "archived_at": datetime.now(UTC).isoformat(),
                    "worker": "violation_remediator",
                },
            )
        except Exception as e:
            logger.warning("ViolationRemediator: rollback archive failed — %s", e)

    # -------------------------------------------------------------------------
    # Summary helpers
    # -------------------------------------------------------------------------

    def _build_violations_summary(self, findings: list[dict[str, Any]]) -> str:
        """Produce a JSON summary of violations for the LLM prompt."""
        violations = []
        for f in findings:
            p = f["payload"]
            violations.append(
                {
                    "rule": p.get("rule", self._target_rule),
                    "file_path": p.get("file_path"),
                    "line_number": p.get("line_number"),
                    "message": p.get("message", ""),
                }
            )
        return json.dumps(violations, indent=2)

    # -------------------------------------------------------------------------
    # Blackboard helpers
    # -------------------------------------------------------------------------

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
                "finding_ids": [f["id"] for f in findings],
            },
        )

    async def _claim_open_findings(self) -> list[dict[str, Any]]:
        """
        Atomically claim open audit.violation findings for the target rule.
        Uses FOR UPDATE SKIP LOCKED to prevent double-claiming across
        concurrent worker instances.
        """
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import get_session

        prefix = f"{_SOURCE_SUBJECT}::{self._target_rule}::%"

        async with get_session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        SELECT id, subject, payload
                        FROM core.blackboard_entries
                        WHERE entry_type = 'finding'
                          AND status = 'open'
                          AND subject LIKE :prefix
                        ORDER BY created_at ASC
                        LIMIT :limit
                        FOR UPDATE SKIP LOCKED
                        """
                    ),
                    {"prefix": prefix, "limit": _CLAIM_LIMIT},
                )
                rows = result.fetchall()

                if not rows:
                    return []

                ids = [str(row[0]) for row in rows]
                await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'claimed'
                        WHERE id = ANY(:ids::uuid[])
                        """
                    ),
                    {"ids": ids},
                )

        findings = []
        for row in rows:
            payload = row[2]
            if isinstance(payload, str):
                payload = json.loads(payload)
            findings.append({"id": str(row[0]), "subject": row[1], "payload": payload})
        return findings

    async def _mark_findings(self, findings: list[dict[str, Any]], status: str) -> None:
        """Update blackboard entry status for a batch of findings."""
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import get_session

        ids = [f["id"] for f in findings]
        async with get_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = :status
                        WHERE id = ANY(:ids::uuid[])
                        """
                    ),
                    {"status": status, "ids": ids},
                )


def _sanitize(text: str) -> str:
    """Remove non-ASCII characters that could corrupt source files."""
    return _NON_ASCII_RE.sub("", text).strip()
