# src/will/workers/doc_worker.py
# ID: will.workers.doc_worker
"""
DocWorker - Constitutional Documentation Sensing Worker.

Responsibility: Detect symbols with missing or degraded documentation and produce
proposals to generate accurate docstrings grounded in code and constitutional intent.

Constitutional standing:
- Declaration:      .intent/workers/doc_worker.yaml
- Class:            acting
- Phase:            runtime
- Permitted tools:  llm.local (LocalCoder / Ollama)
- Approval:         false — proposals execute without human sign-off

LAYER: will/workers — sensing worker. Reads DB for decision context only.
Writing is delegated to DocWriter (body/workers/doc_writer.py).
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from typing import Any

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# Batch size — symbols processed per run
_BATCH_SIZE = 50

# Modules to skip — not documentation targets
_EXCLUDED_MODULE_PREFIXES = (
    "tests.",
    "migrations.",
    "alembic.",
)


# ID: e5f6a7b8-c9d0-1e2f-3a4b-5c6d7e8f9012
class DocWorker(Worker):
    """
    Sensing worker. Detects symbols missing intent, generates accurate
    docstrings via LocalCoder (Ollama), and posts each result as a proposal
    to the blackboard for execution by DocWriter (body layer).

    approval_required: false — proposals run without human approval.
    """

    declaration_name = "doc_worker"

    def __init__(self, cognitive_service: Any) -> None:
        """
        Args:
            cognitive_service: Initialized CognitiveService instance.
                               DocWorker requires llm.local access per its declaration.
        """
        super().__init__()
        self._cognitive = cognitive_service

    # ID: beb75c4b-a000-47ff-a78b-bc022feff531
    async def run(self) -> None:
        """
        Scan for undocumented symbols, generate docstrings via LocalCoder,
        and post each as a proposal to the blackboard for execution by DocWriter.
        """
        await self.post_heartbeat()

        symbols = await self._fetch_undocumented_symbols()

        if not symbols:
            await self.post_report(
                subject="doc_worker.run.complete",
                payload={
                    "proposal_count": 0,
                    "message": "All public symbols are documented.",
                },
            )
            logger.info("DocWorker: nothing to document.")
            return

        logger.info("DocWorker: %d symbols need intent.", len(symbols))

        # Constitutional AI invocation surface — PromptModel governs system prompt,
        # input validation, and output contract.
        # Ref: .intent/rules/ai/prompt_governance.json [ai.prompt.model_required]
        prompt_model = PromptModel.load("docstring_writer")
        client = await self._cognitive.aget_client_for_role(prompt_model.manifest.role)

        proposed = 0
        skipped = 0

        for symbol in symbols[:_BATCH_SIZE]:
            if self._is_excluded(symbol["module"]):
                skipped += 1
                continue

            source_code = await asyncio.to_thread(self._read_source, symbol)
            if not source_code:
                skipped += 1
                logger.debug(
                    "DocWorker: no source for %s — skipped.", symbol["symbol_path"]
                )
                continue

            try:
                docstring = await prompt_model.invoke(
                    context={"source_code": source_code},
                    client=client,
                    user_id="doc_worker",
                )
                docstring = (docstring or "").strip()
                docstring = docstring.encode("ascii", errors="replace").decode("ascii")

                if not docstring:
                    skipped += 1
                    continue

                await self.post_finding(
                    subject=symbol["symbol_path"],
                    payload={
                        "action": "write.docstring",
                        "symbol_path": symbol["symbol_path"],
                        "module": symbol["module"],
                        "qualname": symbol["qualname"],
                        "file_path": symbol["file_path"],
                        "docstring": docstring,
                    },
                )
                proposed += 1

            except ValueError as e:
                # PromptModel output contract violation — skip, don't crash the run
                logger.warning(
                    "DocWorker: PromptModel validation failed for %s: %s",
                    symbol["symbol_path"],
                    e,
                )
                skipped += 1
            except Exception as e:
                logger.error("DocWorker: failed for %s: %s", symbol["symbol_path"], e)
                skipped += 1

        await self.post_report(
            subject="doc_worker.run.complete",
            payload={
                "proposal_count": proposed,
                "skipped_count": skipped,
                "message": f"Run complete. {proposed} proposals posted, {skipped} skipped.",
            },
        )

        logger.info("DocWorker: %d proposals posted, %d skipped.", proposed, skipped)

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    async def _fetch_undocumented_symbols(self) -> list[dict[str, Any]]:
        """Query core.symbols for public symbols with missing or empty intent."""
        from body.services.service_registry import service_registry

        svc = await service_registry.get_doc_service()
        return await svc.fetch_undocumented_symbols()

    def _read_source(self, symbol: dict[str, Any]) -> str | None:
        """
        Extract source code for a symbol using AST lookup by qualname.
        Falls back to full file if AST lookup fails.
        """
        try:
            file_path = (Path("src") / symbol["module"].replace(".", "/")).with_suffix(
                ".py"
            )
            if not file_path.exists():
                return None

            source = file_path.read_text(encoding="utf-8")
            lines = source.splitlines()

            simple_name = symbol["qualname"].split(".")[-1]
            try:
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        if node.name == simple_name:
                            start = node.lineno - 1
                            end = getattr(node, "end_lineno", start + 40)
                            return "\n".join(lines[start:end])
            except SyntaxError:
                pass

            return "\n".join(lines[:60])

        except Exception as e:
            logger.debug(
                "DocWorker: could not read source for %s: %s",
                symbol["symbol_path"],
                e,
            )
            return None

    def _is_excluded(self, module: str) -> bool:
        """Check if a module is excluded from documentation generation."""
        return any(module.startswith(prefix) for prefix in _EXCLUDED_MODULE_PREFIXES)
