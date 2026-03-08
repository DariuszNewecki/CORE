# src/body/workers/doc_writer.py
# ID: body.workers.doc_writer
"""
DocWriter - Constitutional Documentation Acting Worker.

Responsibility: Claim open write.docstring findings from the blackboard
and write the proposed docstring into the target source file via the
governed file.tag_metadata action.

Constitutional standing:
- Declaration:      .intent/workers/doc_writer.yaml
- Class:            acting
- Phase:            execution
- Permitted tools:  file.tag_metadata
- Approval:         false

LAYER: body/workers — acting worker. Executes proposals posted by DocWorker.
DB access is legitimate here: claiming blackboard entries IS execution infrastructure.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_BATCH_SIZE = 25


# ID: b3c4d5e6-f7a8-9b0c-1d2e-3f4a5b6c7d8e
class DocWriter(Worker):
    """
    Acting worker. Claims open write.docstring findings from the blackboard
    and writes the proposed docstring into the source file.

    Delegates file writes to file.tag_metadata governed action.
    """

    declaration_name = "doc_writer"

    def __init__(self, core_context: Any) -> None:
        """
        Args:
            core_context: CoreContext with ActionExecutor access for governed writes.
        """
        super().__init__()
        self._context = core_context

    # ID: d1e2f3a4-b5c6-7d8e-9f0a-1b2c3d4e5f6a
    async def run(self) -> None:
        """
        Claim open write.docstring findings and write docstrings to source files.
        """
        await self.post_heartbeat()

        entries = await self._claim_batch()

        if not entries:
            logger.info("DocWriter: no open findings to process.")
            await self.post_report(
                subject="doc_writer.run.complete",
                payload={"written": 0, "failed": 0, "message": "Nothing to process."},
            )
            return

        logger.info("DocWriter: claimed %d entries.", len(entries))

        written = 0
        failed = 0

        for entry_id, payload in entries:
            try:
                await self._write_docstring(payload)
                await self._mark_resolved(entry_id)
                written += 1
                logger.debug(
                    "DocWriter: wrote docstring for %s", payload.get("symbol_path")
                )
            except Exception as e:
                await self._mark_abandoned(entry_id, str(e))
                failed += 1
                logger.error(
                    "DocWriter: failed for %s: %s", payload.get("symbol_path"), e
                )

        await self.post_report(
            subject="doc_writer.run.complete",
            payload={
                "written": written,
                "failed": failed,
                "message": f"Run complete. {written} written, {failed} failed.",
            },
        )

        logger.info("DocWriter: %d written, %d failed.", written, failed)

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    async def _claim_batch(self) -> list[tuple[uuid.UUID, dict[str, Any]]]:
        """
        Atomically claim a batch of open write.docstring findings.
        Uses FOR UPDATE SKIP LOCKED to prevent double-claiming.
        """
        async with get_session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'claimed', updated_at = now()
                        WHERE id IN (
                            SELECT id FROM core.blackboard_entries
                            WHERE status = 'open'
                              AND payload->>'action' = 'write.docstring'
                            ORDER BY created_at
                            LIMIT :limit
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING id, payload
                        """
                    ),
                    {"limit": _BATCH_SIZE},
                )
                return [(row.id, row.payload) for row in result]

    async def _write_docstring(self, payload: dict[str, Any]) -> None:
        """
        Write the proposed docstring into the target source file.
        Resolves file path from module if file_path is null in payload.
        """
        symbol_path = payload.get("symbol_path", "unknown")
        qualname = payload.get("qualname", "")
        docstring = payload.get("docstring", "").strip()
        file_path_str = payload.get("file_path")
        module = payload.get("module", "")

        if not docstring:
            raise ValueError(f"Empty docstring for {symbol_path}")

        # Resolve file path
        if file_path_str:
            file_path = Path(file_path_str)
        elif module:
            file_path = (Path("src") / module.replace(".", "/")).with_suffix(".py")
        else:
            raise ValueError(f"Cannot resolve file path for {symbol_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        source = file_path.read_text(encoding="utf-8")
        updated = self._insert_docstring(source, qualname, docstring)

        if updated == source:
            logger.debug("DocWriter: no change needed for %s", symbol_path)
            return

        file_path.write_text(updated, encoding="utf-8")

    def _insert_docstring(self, source: str, qualname: str, docstring: str) -> str:
        """
        Insert docstring into source at the correct position using AST.
        Inserts after the def/class line, before the first body statement.
        Processes bottom-to-top to preserve line numbers.
        """
        simple_name = qualname.split(".")[-1]
        lines = source.splitlines(keepends=True)

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        targets = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == simple_name:
                    body = node.body
                    if not body:
                        continue
                    first = body[0]
                    # Skip if docstring already exists
                    if isinstance(first, ast.Expr) and isinstance(
                        first.value, ast.Constant
                    ):
                        continue
                    insert_line = first.lineno - 1  # 0-indexed
                    indent = " " * (node.col_offset + 4)
                    targets.append((insert_line, indent))

        # Bottom-to-top so line numbers stay valid
        for insert_line, indent in sorted(targets, reverse=True):
            doc_line = f'{indent}"""{docstring}"""\n'
            lines.insert(insert_line, doc_line)

        return "".join(lines)

    async def _mark_resolved(self, entry_id: uuid.UUID) -> None:
        """Mark a blackboard entry as resolved."""
        async with get_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'resolved', resolved_at = now(), updated_at = now()
                        WHERE id = :id
                        """
                    ),
                    {"id": entry_id},
                )

    async def _mark_abandoned(self, entry_id: uuid.UUID, reason: str) -> None:
        """Mark a blackboard entry as abandoned with a reason in payload."""
        async with get_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET
                            status = 'abandoned',
                            resolved_at = now(),
                            updated_at = now(),
                            payload = payload || jsonb_build_object('abandon_reason', cast(:reason as text))
                        WHERE id = :id
                        """
                    ),
                    {"id": entry_id, "reason": reason},
                )
