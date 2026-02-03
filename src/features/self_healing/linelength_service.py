# src/features/self_healing/linelength_service.py
# ID: 38f408b5-3490-4fb8-8bf4-c09b33ed5af8

"""
Implements the 'fix line-lengths' command, an AI-powered tool to
refactor code for better readability by adhering to line length policies.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.exceptions import CoreError
from shared.logger import getLogger
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


# ID: 6515f0dd-bea7-474e-894c-74c077d12857
class LineLengthServiceError(CoreError):
    """Raised when line length service fails."""


async def _async_fix_line_lengths(
    context: CoreContext, files_to_process: list[Path], dry_run: bool
):
    """
    Async core logic for finding and fixing all line length violations.
    Mutations are routed through the governed ActionExecutor.
    """
    logger.info(
        "Scanning %s files for lines longer than 100 characters...",
        len(files_to_process),
    )

    # Resolve Prompt via PathResolver (SSOT)
    try:
        prompt_path = settings.paths.prompt("fix_line_length")
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except Exception:
        # Fallback to logical path if resolver is not fully initialized
        prompt_path = settings.MIND / "prompts" / "fix_line_length.prompt"
        if not prompt_path.exists():
            logger.error(
                "Prompt template 'fix_line_length' not found at %s. Aborting.",
                prompt_path,
            )
            return
        prompt_template = prompt_path.read_text(encoding="utf-8")

    executor = ActionExecutor(context)
    cognitive_service = context.cognitive_service
    fixer_client = await cognitive_service.aget_client_for_role("CodeStyleFixer")
    auditor_context = AuditorContext(REPO_ROOT)
    await auditor_context.load_knowledge_graph()

    files_with_long_lines = []
    for file_path in files_to_process:
        try:
            # Check for actual violations before calling LLM
            content = file_path.read_text(encoding="utf-8")
            if any(len(line) > 100 for line in content.splitlines()):
                files_with_long_lines.append(file_path)
        except Exception:
            continue

    if not files_with_long_lines:
        logger.info("✅ No files with long lines found.")
        return

    logger.info("Found %s file(s) with long lines to fix.", len(files_with_long_lines))

    # Execution Loop
    write_mode = not dry_run
    for file_path in files_with_long_lines:
        try:
            rel_path = str(file_path.relative_to(REPO_ROOT))
            original_content = file_path.read_text(encoding="utf-8")

            # Will: Ask AI to refactor for line length
            final_prompt = prompt_template.replace("{source_code}", original_content)
            corrected_code = await fixer_client.make_request_async(
                final_prompt, user_id="line_length_fixer_agent"
            )

            if corrected_code and corrected_code.strip() != original_content.strip():
                # Mandatory Pre-flight Validation
                validation_result = await validate_code_async(
                    rel_path,
                    corrected_code,
                    quiet=True,
                    auditor_context=auditor_context,
                )

                if validation_result["status"] == "clean":
                    # CONSTITUTIONAL GATEWAY: Route through ActionExecutor for governance
                    result = await executor.execute(
                        action_id="file.edit",
                        write=write_mode,
                        file_path=rel_path,
                        code=validation_result["code"],
                    )

                    if result.ok:
                        status = "Fixed" if write_mode else "Proposed (Dry Run)"
                        logger.info("   -> [%s] %s", status, rel_path)
                    else:
                        logger.error(
                            "   -> [BLOCKED] %s: %s", rel_path, result.data.get("error")
                        )
                else:
                    logger.warning(
                        "Skipping %s: AI-generated code failed validation.",
                        rel_path,
                    )
        except Exception as e:
            logger.error("Could not process %s: %s", file_path.name, e)


# ID: 38f408b5-3490-4fb8-8bf4-c09b33ed5af8
async def fix_line_lengths(
    context: CoreContext,
    file_path: Path | str | None = None,
    dry_run: bool = True,
) -> None:
    """Uses an AI agent to refactor files with lines longer than 100 characters via governed actions."""
    if file_path:
        candidate = Path(file_path)
        if not candidate.is_file():
            logger.error("Provided file does not exist or is not a file: %s", file_path)
            raise LineLengthServiceError(
                f"Provided file does not exist: {file_path}", exit_code=1
            )
        target_path = candidate
    else:
        target_path = None

    files_to_scan = []
    if target_path:
        files_to_scan.append(target_path)
    else:
        src_dir = settings.paths.repo_root / "src"
        files_to_scan.extend(src_dir.rglob("*.py"))

    await _async_fix_line_lengths(context, files_to_scan, dry_run)
