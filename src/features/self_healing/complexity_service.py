# src/features/self_healing/complexity_service.py
# ID: 453e06ba-139f-427c-bbe3-ff590640b766
"""Complexity Outlier Refactoring Service - Main Orchestrator.

PURIFIED (V2.7.4)
- Removed direct 'settings' import to satisfy architecture.boundary.settings_access.
- Uses repo_root derived from CoreContext for all path resolution.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from mind.governance.audit_context import AuditorContext
from shared.logger import getLogger
from shared.utils.parsing import parse_write_blocks
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: e24a5930-0d18-46bf-b41b-67a0c8273e76
async def _async_complexity_outliers(
    context: CoreContext,
    file_path: Path | None,
    dry_run: bool,
) -> None:
    """Core logic for identifying and refactoring complexity outliers."""
    if not file_path:
        logger.error("Please provide a specific file path to refactor.")
        return

    # Constitutional fix: use context root instead of global settings
    repo_root = context.git_service.repo_path

    try:
        rel_target = str(file_path.relative_to(repo_root))
    except Exception:
        # If caller passes an already-relative path-like, keep it stable
        rel_target = str(file_path)

    logger.info("Starting complexity refactor cycle for: %s", rel_target)

    # 1) Setup governed environment
    executor = ActionExecutor(context)
    cognitive_service = context.cognitive_service

    auditor_context = AuditorContext(repo_root)
    await auditor_context.load_knowledge_graph()

    try:
        # 2) Get AI architectural plan (Will)
        source_code = file_path.read_text(encoding="utf-8")

        # Use path resolver from context to find prompt
        prompt_path = context.path_resolver.prompt("refactor_outlier")
        prompt_template = prompt_path.read_text(encoding="utf-8").replace(
            "{source_code}",
            source_code,
        )

        refactor_client = await cognitive_service.aget_client_for_role(
            "RefactoringArchitect"
        )
        response = await refactor_client.make_request_async(
            prompt_template,
            user_id="refactoring_agent",
        )

        refactoring_plan = parse_write_blocks(response)
        if not refactoring_plan:
            raise ValueError("No valid [[write:]] blocks found in AI response.")

        # 3) Validation phase
        validated_code_plan: dict[str, str] = {}
        for path, code in refactoring_plan.items():
            val_result = await validate_code_async(
                path,
                str(code),
                auditor_context=auditor_context,
            )
            if val_result.get("status") == "dirty":
                raise RuntimeError(
                    f"AI generated invalid code for '{path}': {val_result.get('violations')}"
                )
            validated_code_plan[path] = val_result["code"]

        # 4) Governed execution (Body)
        write_mode = not dry_run

        # Step A: delete the original outlier
        del_result = await executor.execute(
            action_id="file.delete",
            write=write_mode,
            file_path=rel_target,
        )

        if not del_result.ok:
            logger.error(
                "Refactor aborted: Could not delete original file: %s",
                del_result.data.get("error"),
            )
            return

        # Step B: create the new, refactored files
        for path, new_code in validated_code_plan.items():
            create_result = await executor.execute(
                action_id="file.create",
                write=write_mode,
                file_path=path,
                code=new_code,
            )

            if create_result.ok:
                status = "Created" if write_mode else "Proposed"
                logger.info("   -> [%s] %s", status, path)
            else:
                logger.error(
                    "   -> [FAILED] %s: %s",
                    path,
                    create_result.data.get("error"),
                )

        logger.info(
            "Refactoring orchestration complete. Sync with 'core-admin dev sync' to update graph."
        )

    except Exception as e:
        logger.error("Refactoring failed for %s: %s", rel_target, e, exc_info=True)


# ID: dea3fb62-d97e-4379-9550-4821eead252d
async def complexity_outliers(
    context: CoreContext,
    file_path: Path | None,
    dry_run: bool = True,
) -> None:
    """Public entry point for complexity refactoring workflow."""
    await _async_complexity_outliers(context, file_path, dry_run)
