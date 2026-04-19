# src/body/workers/prompt_artifact_writer.py
# ID: body.workers.prompt_artifact_writer
"""
PromptArtifactWriter - Constitutional Compliance Acting Worker.

Responsibility: For each approved prompt extraction on the blackboard,
generate and write the three PromptModel artifact files to var/prompts/.

Constitutional standing:
- Declaration:      .intent/workers/prompt_artifact_writer.yaml
- Class:            acting
- Phase:            execution
- Permitted tools:  llm.architect, file.write
- Approval:         true

LAYER: body/workers — acting worker. Writes to var/prompts/ only via
FileHandler (IntentGuard enforced). No src/ writes.
"""

from __future__ import annotations

import json
import re
from typing import Any

from shared.ai.response_parser import extract_json
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_SOURCE_SUBJECT = "prompt.extraction"
_ARTIFACT_SUBJECT = "prompt.artifact"

# Non-ASCII character filter for DB safety (PostgreSQL SQL_ASCII)
_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")

_CLAIM_LIMIT = 25


# ID: c3d4e5f6-a7b8-9012-cdef-123456789012
class PromptArtifactWriter(Worker):
    """
    Acting worker. Claims open prompt.extraction findings from the blackboard,
    invokes the prompt_artifact_generator PromptModel to produce three artifact
    files, writes them to var/prompts/<suggested_name>/ via FileHandler,
    and posts a completion finding to the blackboard.

    approval_required: true — writes to the filesystem.
    """

    declaration_name = "prompt_artifact_writer"

    def __init__(self, core_context: Any) -> None:
        """
        Args:
            core_context: Initialized CoreContext. Provides cognitive_service,
                          file_handler, and git_service.
        """
        super().__init__()
        self._core_context = core_context

    # ID: d4e5f6a7-b8c9-0123-defa-234567890123
    async def run(self) -> None:
        """
        Claim open extraction findings, generate PromptModel artifacts via
        LLM, write files via FileHandler, post results to blackboard.
        """
        await self.post_heartbeat()

        findings = await self._claim_open_extractions()

        if not findings:
            await self.post_report(
                subject="prompt_artifact_writer.run.complete",
                payload={
                    "written": 0,
                    "message": "No open extraction findings to process.",
                },
            )
            logger.info("PromptArtifactWriter: no open extractions.")
            return

        logger.info("PromptArtifactWriter: %d extractions to process.", len(findings))

        from shared.ai.prompt_model import PromptModel

        model = PromptModel.load("prompt_artifact_generator")

        client = await self._core_context.cognitive_service.aget_client_for_role(
            model.manifest.role
        )
        file_handler = self._core_context.file_handler

        written = 0
        failed = 0

        for finding in findings:
            payload = finding["payload"]
            extraction_id: str = finding["id"]
            file_path: str = payload["file_path"]
            line_number: int = payload["line_number"]
            prompt_text: str = payload.get("prompt_text", "")
            suggested_name: str = payload.get("suggested_name", "")
            input_vars: list[str] = payload.get("input_vars", [])

            if not suggested_name:
                logger.warning(
                    "PromptArtifactWriter: no suggested_name for %s:%s — skipping",
                    file_path,
                    line_number,
                )
                await self._mark_finding(extraction_id, "abandoned")
                failed += 1
                continue

            cognitive_role = _infer_role(file_path)

            try:
                raw = await model.invoke(
                    context={
                        "file_path": file_path,
                        "suggested_name": suggested_name,
                        "prompt_text": prompt_text,
                        "input_vars": json.dumps(input_vars),
                        "cognitive_role": cognitive_role,
                    },
                    client=client,
                    user_id="prompt_artifact_writer",
                )
            except Exception as e:
                logger.warning(
                    "PromptArtifactWriter: LLM invocation failed for %s — %s",
                    suggested_name,
                    e,
                )
                await self._mark_finding(extraction_id, "abandoned")
                failed += 1
                continue

            try:
                artifact = extract_json(raw)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    "PromptArtifactWriter: JSON parse failed for %s — %s | raw[:200]=%r",
                    suggested_name,
                    e,
                    raw[:200],
                )
                await self._mark_finding(extraction_id, "abandoned")
                failed += 1
                continue

            model_yaml = _sanitize(artifact.get("model_yaml", ""))
            system_txt = _sanitize(artifact.get("system_txt", ""))
            user_txt = _sanitize(artifact.get("user_txt", ""))

            if not model_yaml or not system_txt or not user_txt:
                logger.warning(
                    "PromptArtifactWriter: incomplete artifact for %s — skipping",
                    suggested_name,
                )
                await self._mark_finding(extraction_id, "abandoned")
                failed += 1
                continue

            try:
                base = f"var/prompts/{suggested_name}"
                file_handler.write_runtime_text(f"{base}/model.yaml", model_yaml)
                file_handler.write_runtime_text(f"{base}/system.txt", system_txt)
                file_handler.write_runtime_text(f"{base}/user.txt", user_txt)
            except Exception as e:
                logger.warning(
                    "PromptArtifactWriter: file write failed for %s — %s",
                    suggested_name,
                    e,
                )
                await self._mark_finding(extraction_id, "abandoned")
                failed += 1
                continue

            subject = f"{_ARTIFACT_SUBJECT}::{file_path}::{line_number}"
            await self.post_finding(
                subject=subject,
                payload={
                    "source_extraction_id": extraction_id,
                    "file_path": file_path,
                    "line_number": line_number,
                    "artifact_name": suggested_name,
                    "artifact_path": f"var/prompts/{suggested_name}",
                    "cognitive_role": cognitive_role,
                    "status": "written",
                },
            )

            await self._mark_finding(extraction_id, "resolved")

            written += 1
            logger.info(
                "PromptArtifactWriter: wrote var/prompts/%s/ (%s:%s)",
                suggested_name,
                file_path,
                line_number,
            )

        await self.post_report(
            subject="prompt_artifact_writer.run.complete",
            payload={
                "written": written,
                "failed": failed,
                "message": f"Run complete. {written} artifacts written, {failed} failed.",
            },
        )

        logger.info("PromptArtifactWriter: %d written, %d failed.", written, failed)

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    async def _claim_open_extractions(self) -> list[dict[str, Any]]:
        """
        Atomically claim open prompt.extraction findings.
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
            findings.append(
                {
                    "id": str(row[0]),
                    "subject": row[1],
                    "payload": payload,
                }
            )
        return findings

    async def _mark_finding(self, finding_id: str, status: str) -> None:
        """Update the status of a blackboard finding by ID."""
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import get_session

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


def _sanitize(value: str) -> str:
    """Strip non-ASCII characters that PostgreSQL SQL_ASCII cannot store."""
    if not isinstance(value, str):
        return str(value)
    return _NON_ASCII_RE.sub("?", value)


def _infer_role(file_path: str) -> str:
    """
    Infer an appropriate cognitive role from the file path.
    Conservative defaults: most tasks go to LocalCoder; strategic/governance
    files get Architect.
    """
    if any(
        seg in file_path
        for seg in ("strategic_auditor", "assumption_extractor", "authority_package")
    ):
        return "Architect"
    if any(seg in file_path for seg in ("planner", "orchestration", "interpreter")):
        return "Planner"
    return "LocalCoder"
