# src/features/self_healing/clarity_service.py

"""
Implements the 'fix clarity' command, using an AI agent to perform
principled refactoring of Python code for improved readability and simplicity.
"""

from __future__ import annotations

from pathlib import Path

from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 8bf2ad74-d73b-4b9d-b711-c0980f773afe
async def fix_clarity(context: CoreContext, file_path: Path, dry_run: bool):
    """
    Refactors the provided file for clarity with optional dry run.
    """
    logger.info("Analyzing '%s' for clarity improvements...", file_path.name)
    cognitive_service = context.cognitive_service

    prompt_template = (
        settings.MIND / "mind/prompts" / "refactor_for_clarity.prompt"
    ).read_text()
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
        logger.info("AI Architect found no clarity improvements to make.")
        return

    if dry_run:
        logger.info("-- DRY RUN: Would refactor %s --", file_path.name)
    else:
        file_path.write_text(refactored_code, "utf-8")
        logger.info("Successfully refactored '%s' for clarity.", file_path.name)
