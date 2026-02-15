# src/features/self_healing/clarity_service.py
# ID: 8bf2ad74-d73b-4b9d-b711-c0980f773afe

"""
Implements the 'fix clarity' command, using an AI agent to perform
principled refactoring of Python code for improved readability and simplicity.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: b7ece8ed-0753-476f-be7d-d6e36048d582
async def fix_clarity(context: CoreContext, file_path: Path, dry_run: bool):
    """
    Refactors the provided file for clarity via governed atomic actions.
    """
    rel_path = str(file_path.relative_to(settings.REPO_PATH))
    logger.info("🔍 Analyzing '%s' for clarity improvements...", rel_path)

    # 1. Initialize Services
    executor = ActionExecutor(context)
    cognitive_service = context.cognitive_service

    # Resolve Prompt via PathResolver (SSOT)
    # CONSTITUTIONAL FIX: Removed fallback to settings.MIND (.intent is read-only).
    # Prompts must reside in var/prompts/ as managed by the PathResolver.
    prompt_path = settings.paths.prompt("refactor_for_clarity")

    if not prompt_path.exists():
        logger.error(
            "Constitutional prompt 'refactor_for_clarity.prompt' missing from var/prompts/. Aborting."
        )
        return

    try:
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read prompt template at %s: %s", prompt_path, e)
        return

    # 2. Get AI Proposal (Will)
    original_code = file_path.read_text("utf-8")
    final_prompt = prompt_template.replace("{source_code}", original_code)

    refactor_client = await cognitive_service.aget_client_for_role(
        "RefactoringArchitect"
    )

    logger.info("Asking AI Architect to refactor for clarity...")
    refactored_code = await refactor_client.make_request_async(
        final_prompt,
        user_id="clarity_fixer_agent",
    )

    if not refactored_code.strip() or refactored_code.strip() == original_code.strip():
        logger.info("✅ AI Architect found no clarity improvements to make.")
        return

    # 3. Pre-flight Validation
    # Refactoring is high-risk; we must ensure the result is clean.
    from mind.governance.audit_context import AuditorContext

    auditor_context = AuditorContext(settings.REPO_PATH)

    validation_result = await validate_code_async(
        rel_path, refactored_code, quiet=True, auditor_context=auditor_context
    )

    if validation_result["status"] == "dirty":
        logger.warning(
            "Skipping refactor for %s: AI proposal failed validation.", rel_path
        )
        return

    # 4. Governed Execution (Body)
    write_mode = not dry_run
    result = await executor.execute(
        action_id="file.edit",
        write=write_mode,
        file_path=rel_path,
        code=validation_result["code"],
    )

    if result.ok:
        status = "Refactored" if write_mode else "Proposed (Dry Run)"
        logger.info("   -> [%s] %s", status, rel_path)
    else:
        logger.error("   -> [BLOCKED] %s: %s", rel_path, result.data.get("error"))


# Alias for backward compatibility with older CLI wrappers if necessary
_async_fix_clarity = fix_clarity
