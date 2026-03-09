# src/will/workers/prompt_extractor_worker.py
# ID: will.workers.prompt_extractor_worker
"""
PromptExtractorWorker - Constitutional Compliance Sensing Worker.

Responsibility: For each unprocessed ai.prompt.model_required violation on
the blackboard, read the violating source file and extract the inline prompt
string passed to make_request_async().

Constitutional standing:
- Declaration:      .intent/workers/prompt_extractor_worker.yaml
- Class:            sensing
- Phase:            runtime
- Permitted tools:  llm.local
- Approval:         false

LAYER: will/workers — sensing worker. Receives CoreContext via constructor
injection. Reads source files (read-only). Posts extraction results to the
blackboard. Does not write source files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_SOURCE_RULE = "ai.prompt.model_required"
_EXTRACTION_SUBJECT = "prompt.extraction"

# Lines of context around the violation to send to the LLM
_CONTEXT_LINES = 40


# ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
class PromptExtractorWorker(Worker):
    """
    Sensing worker. Claims open ai.prompt.model_required findings from the
    blackboard, reads the violating source file around the reported line,
    invokes the prompt_extractor PromptModel to extract the inline prompt,
    and posts the extraction result as a new blackboard finding.

    Low-confidence extractions (< 0.5) are posted with status 'needs_human'.
    High-confidence extractions are posted with status 'open' for downstream
    processing by PromptArtifactWriter.

    No file writes. approval_required: false — findings are observations.
    """

    declaration_name = "prompt_extractor_worker"

    def __init__(self, core_context: Any) -> None:
        """
        Args:
            core_context: Initialized CoreContext. Provides cognitive_service
                          for LLM access and git_service for repo_path.
        """
        super().__init__()
        self._core_context = core_context

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789012
    async def run(self) -> None:
        """
        Claim unprocessed violation findings, extract prompts via LLM,
        post extraction results to the blackboard.
        """
        await self.post_heartbeat()

        findings = await self._fetch_open_findings()

        if not findings:
            await self.post_report(
                subject="prompt_extractor_worker.run.complete",
                payload={
                    "processed": 0,
                    "message": "No unprocessed findings to extract.",
                },
            )
            logger.info("PromptExtractorWorker: no open findings.")
            return

        logger.info("PromptExtractorWorker: %d findings to process.", len(findings))

        client = await self._core_context.cognitive_service.aget_client_for_role(
            "LocalCoder"
        )

        from shared.ai.prompt_model import PromptModel

        model = PromptModel.load("prompt_extractor")

        repo_path: Path = self._core_context.git_service.repo_path

        processed = 0
        failed = 0

        for finding in findings:
            payload = finding["payload"]
            file_path_str: str = payload["file_path"]
            line_number: int = payload["line_number"]
            finding_id: str = finding["id"]

            try:
                source_code = self._extract_context(
                    repo_path / file_path_str, line_number
                )
            except (FileNotFoundError, OSError) as e:
                logger.warning(
                    "PromptExtractorWorker: cannot read %s: %s", file_path_str, e
                )
                await self._mark_finding(finding_id, "abandoned")
                failed += 1
                continue

            try:
                raw = await model.invoke(
                    context={
                        "file_path": file_path_str,
                        "line_number": str(line_number),
                        "source_code": source_code,
                    },
                    client=client,
                    user_id="prompt_extractor_worker",
                )
                extraction = json.loads(raw)
            except Exception as e:
                logger.warning(
                    "PromptExtractorWorker: LLM extraction failed for %s:%s — %s",
                    file_path_str,
                    line_number,
                    e,
                )
                await self._mark_finding(finding_id, "abandoned")
                failed += 1
                continue

            confidence: float = float(extraction.get("confidence", 0.0))
            needs_human = (
                confidence < 0.5 or extraction.get("prompt_text") == "needs_human"
            )
            extraction_status = "needs_human" if needs_human else "open"

            subject = f"{_EXTRACTION_SUBJECT}::{file_path_str}::{line_number}"

            await self.post_finding(
                subject=subject,
                payload={
                    "source_finding_id": finding_id,
                    "source_rule": _SOURCE_RULE,
                    "file_path": file_path_str,
                    "line_number": line_number,
                    "prompt_text": _sanitize(extraction.get("prompt_text", "")),
                    "suggested_name": _sanitize(extraction.get("suggested_name", "")),
                    "input_vars": [
                        _sanitize(v) for v in extraction.get("input_vars", [])
                    ],
                    "confidence": confidence,
                    "needs_human": needs_human,
                    "status": extraction_status,
                },
            )

            # Mark source finding as claimed so it won't be reprocessed
            await self._mark_finding(finding_id, "claimed")

            processed += 1
            logger.debug(
                "PromptExtractorWorker: extracted %s:%s (confidence=%.2f, needs_human=%s)",
                file_path_str,
                line_number,
                confidence,
                needs_human,
            )

        await self.post_report(
            subject="prompt_extractor_worker.run.complete",
            payload={
                "processed": processed,
                "failed": failed,
                "message": f"Run complete. {processed} extracted, {failed} failed.",
            },
        )

        logger.info(
            "PromptExtractorWorker: %d extracted, %d failed.", processed, failed
        )

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _extract_context(self, file_path: Path, line_number: int) -> str:
        """
        Read the source file and return _CONTEXT_LINES lines centred on
        line_number. Returns the entire file if it is shorter than the window.
        """
        lines = file_path.read_text(encoding="utf-8").splitlines()
        # line_number is 1-based
        start = max(0, line_number - 1 - (_CONTEXT_LINES // 2))
        end = min(len(lines), start + _CONTEXT_LINES)
        start = max(0, end - _CONTEXT_LINES)
        return "\n".join(lines[start:end])

    async def _fetch_open_findings(self) -> list[dict[str, Any]]:
        """
        Return all open ai.prompt.model_required findings not yet claimed.
        """
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import (
            get_session,
        )

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, subject, payload
                    FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject LIKE :prefix
                      AND status = 'open'
                    ORDER BY created_at ASC
                    """
                ),
                {"prefix": f"{_SOURCE_RULE}::%"},
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
            findings.append(
                {
                    "id": str(row[0]),
                    "subject": row[1],
                    "payload": payload,
                }
            )
        return findings

    async def _mark_finding(self, finding_id: str, status: str) -> None:
        """
        Update the status of a blackboard finding by ID.
        """
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import (
            get_session,
        )

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.blackboard_entries
                    SET status = :status
                    WHERE id = :id
                    """
                ),
                {"status": status, "id": finding_id},
            )
            await session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Matches any character outside the ASCII printable range + common whitespace
_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")


def _sanitize(value: str) -> str:
    """
    Strip characters that PostgreSQL SQL_ASCII encoding cannot store.
    Replaces non-ASCII and non-printable characters with '?'.
    Preserves tab, newline, and carriage return.
    """
    if not isinstance(value, str):
        return str(value)
    return _NON_ASCII_RE.sub("?", value)
