# src/features/self_healing/alignment_orchestrator.py

"""
AlignmentOrchestrator (The Police Agent)
Enforces Constitutional Integrity at the file level. Refactored (V2.3).
"""

from __future__ import annotations

import time
from typing import Any

from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.tools.symbol_finder import SymbolFinder

from .alignment.persistence import record_action_result, update_system_memory
from .alignment.sandbox import verify_import_safety
from .alignment.specialists import SpecialistDispatcher


logger = getLogger(__name__)


# ID: e776b3ae-a7b1-4737-adcd-bf9714a35543
class AlignmentOrchestrator:
    def __init__(self, cognitive_service: CognitiveService):
        self.cognitive = cognitive_service
        self.symbol_finder = SymbolFinder()
        self.dispatcher = SpecialistDispatcher(cognitive_service, self.symbol_finder)

    # ID: bd0aa07e-317d-4443-9c93-424254093cd5
    async def align_file(self, file_path: str, write: bool = False) -> dict[str, Any]:
        start_time = time.time()
        logger.info("👮 Police Agent: Inspecting %s (write_mode=%s)", file_path, write)

        from mind.governance.audit_context import AuditorContext
        from mind.governance.filtered_audit import run_filtered_audit

        # 1. THE WARRANT
        auditor_ctx = AuditorContext(settings.REPO_PATH)
        findings, _, _ = await run_filtered_audit(auditor_ctx, rule_patterns=[r".*"])
        file_violations = [
            f
            for f in findings
            if f.get("file_path") == file_path
            and "engine_missing" not in str(f.get("check_id"))
        ]

        is_importable, current_error = await verify_import_safety(file_path)

        if not file_violations and is_importable:
            logger.info("✅ %s is 100%% Aligned.", file_path)
            await record_action_result(
                file_path=file_path,
                ok=True,
                duration_ms=int((time.time() - start_time) * 1000),
                action_metadata={"violations_found": 0, "already_compliant": True},
            )
            return {"status": "compliant", "file": file_path}

        # 2. THE ACTION
        modified, errors = False, []
        for violation in file_violations:
            rule_id = violation.get("check_id")
            try:
                if rule_id == "code_standards.max_file_lines":
                    if await self.dispatcher.trigger_modularizer(file_path, write):
                        modified = True
                elif rule_id == "layout.src_module_header":
                    if await self.dispatcher.heal_structural_clerk(
                        file_path, "header", write
                    ):
                        modified = True
                elif rule_id == "linkage.assign_ids":
                    if await self.dispatcher.heal_structural_clerk(
                        file_path, "ids", write
                    ):
                        modified = True
                else:
                    if await self.dispatcher.trigger_generic_repair(
                        file_path, violation, write
                    ):
                        modified = True
            except Exception as e:
                errors.append(f"Failed to heal {rule_id}: {e}")

        if not is_importable:
            try:
                if await self.dispatcher.trigger_logic_repair(
                    file_path, current_error, write
                ):
                    modified = True
            except Exception as e:
                errors.append(f"Failed logic repair: {e}")

        # 3. THE BOOKING
        if modified and write:
            try:
                await update_system_memory(file_path, write=write)
            except Exception as e:
                errors.append(f"Failed to update system memory: {e}")

        # 4. THE RECORD
        final_ok = modified and not errors
        await record_action_result(
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
