# src/features/self_healing/alignment_orchestrator.py

"""
AlignmentOrchestrator (The Police Agent)
Ensures a file is 100% compliant with the CORE Constitution and SSOT.

Workflow:
1. The Warrant: Run Constitutional Audit to find violations.
2. The Action: Dispatch to specialists (Modularizer, Logic Repair, or Clerk).
3. The Booking: Sync with DB and Qdrant to update system memory.
4. The Record: Log outcome to action_results for workflow gate verification.

CONSTITUTIONAL FIX:
- Removed global and local imports of 'get_session' to satisfy 'logic.di.no_global_session'.
- Uses ServiceRegistry for database session acquisition.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from typing import Any

from body.services.service_registry import service_registry
from mind.governance.filtered_audit import run_filtered_audit
from shared.config import settings
from shared.logger import getLogger
from shared.models.action_result import ActionResult
from shared.utils.parsing import extract_python_code_from_response, parse_write_blocks
from will.orchestration.cognitive_service import CognitiveService
from will.tools.symbol_finder import SymbolFinder


logger = getLogger(__name__)


# ID: a2d3e4f5-b6c7-8d9e-0a1b-2c3d4e5f6a7b
class AlignmentOrchestrator:
    """The 'Police Agent' - Enforces Constitutional Integrity at the file level."""

    def __init__(self, cognitive_service: CognitiveService):
        self.cognitive = cognitive_service
        self.symbol_finder = SymbolFinder()

    # ID: 3e4f5a6b-7c8d-9e0f-1a2b-3c4d5e6f7a8b
    async def align_file(self, file_path: str, write: bool = False) -> dict[str, Any]:
        """Runs the 'Total Alignment' protocol on a specific file."""
        start_time = time.time()
        logger.info("👮 Police Agent: Inspecting %s (write_mode=%s)", file_path, write)

        # 1. THE WARRANT: Run Constitutional Audit
        from mind.governance.audit_context import AuditorContext

        auditor_ctx = AuditorContext(settings.REPO_PATH)

        # Check every rule in the Constitution
        findings, _, _ = await run_filtered_audit(auditor_ctx, rule_patterns=[r".*"])

        # STREET SMART: Filter only for REAL violations in THIS file.
        file_violations = [
            f
            for f in findings
            if f.get("file_path") == file_path
            and "engine_missing" not in str(f.get("check_id"))
        ]

        # Pre-emptive Logic Check (Imports/Syntax)
        is_importable, _error_msg = await self._verify_import_safety(file_path)

        if not file_violations and is_importable:
            logger.info("✅ %s is a law-abiding citizen (100%% Aligned).", file_path)

            # Record success to action_results table
            await self._record_action_result(
                file_path=file_path,
                ok=True,
                duration_ms=int((time.time() - start_time) * 1000),
                action_metadata={"violations_found": 0, "already_compliant": True},
            )

            return {"status": "compliant", "file": file_path}

        logger.warning("🚨 %s requires attention. Initiating healing...", file_path)

        # 2. THE ACTION: Dispatch to appropriate specialists
        modified = False
        errors = []

        for violation in file_violations:
            rule_id = violation.get("check_id")

            try:
                # CASE: File too long -> Call Modularizer
                if rule_id == "code_standards.max_file_lines":
                    if await self._trigger_modularizer(file_path, write):
                        modified = True

                # CASE: Header violation -> Call the Clerk
                elif rule_id == "layout.src_module_header":
                    if await self._heal_structural_clerk(file_path, "header", write):
                        modified = True

                # CASE: ID violation -> Call the Clerk
                elif rule_id == "linkage.assign_ids":
                    if await self._heal_structural_clerk(file_path, "ids", write):
                        modified = True

                # CASE: Generic violation
                else:
                    if await self._trigger_generic_repair(file_path, violation, write):
                        modified = True

            except Exception as e:
                error_msg = f"Failed to heal {rule_id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # CASE: Logic drift (broken imports).
        still_unstable, current_error = await self._verify_import_safety(file_path)
        if not still_unstable:
            try:
                if await self._trigger_logic_repair(file_path, current_error, write):
                    modified = True
            except Exception as e:
                error_msg = f"Failed logic repair: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # 3. THE BOOKING: Synchronize SSOT
        if modified and write:
            try:
                await self._update_system_memory(file_path, write=write)
                logger.info(
                    "✅ File %s successfully rehabilitated and synced with SSOT.",
                    file_path,
                )
            except Exception as e:
                error_msg = f"Failed to update system memory: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # 4. THE RECORD: Log result
        final_ok = modified and not errors
        await self._record_action_result(
            file_path=file_path,
            ok=final_ok,
            duration_ms=int((time.time() - start_time) * 1000),
            error_message="; ".join(errors) if errors else None,
            action_metadata={
                "violations_found": len(file_violations),
                "violations_fixed": modified,
                "write_mode": write,
                "errors": errors,
            },
        )

        return {
            "status": "healed" if final_ok else "failed",
            "file": file_path,
            "write_applied": write and modified,
            "errors": errors,
        }

    async def _trigger_modularizer(self, file_path: str, write: bool) -> bool:
        """Agentic healing for God Objects."""
        logger.info("📐 God Object detected. Triggering Modularizer Specialist...")

        prompt_path = settings.paths.prompt("modularizer")
        template = await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")
        source_code = await asyncio.to_thread(
            (settings.REPO_PATH / file_path).read_text, encoding="utf-8"
        )

        final_prompt = template.format(
            file_path=file_path,
            current_lines=len(source_code.splitlines()),
            max_lines=400,
            source_code=source_code,
        )

        agent = await self.cognitive.aget_client_for_role("RefactoringArchitect")
        response = await agent.make_request_async(
            final_prompt, user_id="police_agent_modularizer"
        )

        blocks = parse_write_blocks(response)
        if not blocks:
            logger.error("❌ Modularizer failed to provide actionable write blocks.")
            return False

        if write:
            for path, content in blocks.items():
                await asyncio.to_thread(
                    (settings.REPO_PATH / path).write_text, content, encoding="utf-8"
                )
                logger.info("📦 Modularizer: Created/Updated %s", path)
            return True
        return False

    async def _trigger_logic_repair(
        self, file_path: str, error_msg: str, write: bool
    ) -> bool:
        """Agentic healing for broken imports/drift."""
        logger.info("🧠 Logic drift detected. Triggering Logic Specialist...")

        hints = await self.symbol_finder.get_context_for_import_error(error_msg)
        prompt_path = settings.paths.prompt("logic_alignment")
        template = await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")
        source_code = await asyncio.to_thread(
            (settings.REPO_PATH / file_path).read_text, encoding="utf-8"
        )

        final_prompt = template.format(
            file_path=file_path,
            error_message=error_msg,
            symbol_hints=hints or "Use architectural standards.",
            source_code=source_code,
        )

        agent = await self.cognitive.aget_client_for_role("Coder")
        response = await agent.make_request_async(
            final_prompt, user_id="police_agent_logic"
        )
        fixed_code = extract_python_code_from_response(response)

        if fixed_code and write:
            await asyncio.to_thread(
                (settings.REPO_PATH / file_path).write_text,
                fixed_code,
                encoding="utf-8",
            )
            logger.info("🔧 Logic Specialist: Repaired imports in %s", file_path)
            return True
        return False

    async def _trigger_generic_repair(
        self, file_path: str, violation: dict, write: bool
    ) -> bool:
        """Generic healing for violations not covered by specific handlers."""
        logger.info(
            "🔍 Generic violation %s. Triggering Logic Specialist...",
            violation.get("check_id"),
        )

        source_code = await asyncio.to_thread(
            (settings.REPO_PATH / file_path).read_text, encoding="utf-8"
        )

        prompt_path = settings.paths.prompt("logic_alignment")
        template = await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")

        violation_details = (
            f"Rule: {violation.get('check_id')}\n"
            f"Severity: {violation.get('severity')}\n"
            f"Message: {violation.get('message')}\n"
            f"Line: {violation.get('line_number', 'none')}"
        )

        final_prompt = template.format(
            file_path=file_path,
            error_message=violation_details,
            symbol_hints="Search codebase for similar correct implementations.",
            source_code=source_code,
        )

        agent = await self.cognitive.aget_client_for_role("Coder")
        response = await agent.make_request_async(
            final_prompt, user_id="police_agent_generic"
        )
        fixed_code = extract_python_code_from_response(response)

        if fixed_code and write:
            await asyncio.to_thread(
                (settings.REPO_PATH / file_path).write_text,
                fixed_code,
                encoding="utf-8",
            )
            logger.info("✅ Generic repair applied to %s", file_path)
            return True
        return False

    async def _heal_structural_clerk(
        self, file_path: str, task: str, write: bool
    ) -> bool:
        """Deterministic healing for metadata."""
        if not write:
            return False

        if task == "header":
            from features.self_healing.header_service import HeaderService

            await asyncio.to_thread(
                HeaderService()._fix, [str(settings.REPO_PATH / file_path)]
            )
            return True

        if task == "ids":
            from features.self_healing.id_tagging_service import assign_missing_ids

            # CONSTITUTIONAL FIX: Action handles its own gateway/audit
            # We don't import get_session here.
            await assign_missing_ids(context=None, write=False)
            return True

        return False

    async def _verify_import_safety(self, file_path: str) -> tuple[bool, str]:
        """Sandbox test to ensure the file is 'compilable'."""
        module_path = file_path.replace("src/", "").replace(".py", "").replace("/", ".")
        check_code = f"import {module_path}\nprint('ALIVE')"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(check_code)
            temp_path = f.name

        try:
            src_path = str((settings.REPO_PATH / "src").resolve())
            proc = await asyncio.create_subprocess_exec(
                "env",
                f"PYTHONPATH={src_path}",
                "python3",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(settings.REPO_PATH),
            )
            _stdout, stderr = await proc.communicate()
            return (proc.returncode == 0, stderr.decode("utf-8"))
        finally:
            await asyncio.to_thread(Path(temp_path).unlink, missing_ok=True)

    async def _update_system_memory(self, file_path: str, write: bool):
        """Ensures the State (DB) and Mind (Vectors) match the Body (Code)."""
        # CONSTITUTIONAL FIX: No 'get_session' import.
        # Uses the registry to acquire a session context manager.
        from body.services.service_registry import service_registry
        from features.introspection.sync_service import run_sync_with_db
        from features.introspection.vectorization_service import run_vectorize
        from shared.context import CoreContext

        logger.info(
            "🔄 Booking: Updating Knowledge Graph and Vectors for %s...", file_path
        )
        # Using the primed registry factory helper
        async with service_registry.session() as session:
            # 1. Sync Symbols to DB
            await run_sync_with_db(session)

            # 2. Re-vectorize to Qdrant
            ctx = CoreContext(registry=service_registry)
            await run_vectorize(context=ctx, session=session, dry_run=not write)

    async def _record_action_result(
        self,
        file_path: str,
        ok: bool,
        duration_ms: int,
        error_message: str | None = None,
        action_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record alignment action outcome to action_results table."""
        # CONSTITUTIONAL FIX: Uses service_registry.session() instead of local get_session import.
        async with service_registry.session() as session:
            result = ActionResult(
                action_type="alignment",
                ok=ok,
                file_path=file_path,
                error_message=error_message,
                action_metadata=action_metadata,
                agent_id="alignment_orchestrator",
                duration_ms=duration_ms,
            )
            session.add(result)
            await session.commit()

        logger.debug(
            "📊 Recorded action_result: alignment %s for %s",
            "✓" if ok else "✗",
            file_path,
        )
