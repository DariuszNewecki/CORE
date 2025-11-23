# src/features/self_healing/linelength_service.py

"""
Implements the 'fix line-lengths' command, an AI-powered tool to
refactor code for better readability by adhering to line length policies.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.progress import track

from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.validation_pipeline import validate_code_async

logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


async def _async_fix_line_lengths(
    cognitive_service: CognitiveService, files_to_process: list[Path], dry_run: bool
):
    """Async core logic for finding and fixing all line length violations."""
    logger.info(
        f"Scanning {len(files_to_process)} files for lines longer than 100 characters..."
    )
    prompt_template_path = settings.MIND / "prompts" / "fix_line_length.prompt"
    if not prompt_template_path.exists():
        logger.error(f"Prompt not found at {prompt_template_path}. Cannot proceed.")
        raise typer.Exit(code=1)
    prompt_template = prompt_template_path.read_text(encoding="utf-8")
    fixer_client = await cognitive_service.aget_client_for_role("CodeStyleFixer")
    auditor_context = AuditorContext(REPO_ROOT)
    await auditor_context.load_knowledge_graph()
    files_with_long_lines = []
    for file_path in files_to_process:
        try:
            for line in file_path.read_text(encoding="utf-8").splitlines():
                if len(line) > 100:
                    files_with_long_lines.append(file_path)
                    break
        except Exception:
            continue
    if not files_with_long_lines:
        logger.info("✅ No files with long lines found. Nothing to do.")
        return
    logger.info(f"Found {len(files_with_long_lines)} file(s) with long lines to fix.")
    modification_plan = {}
    for file_path in track(
        files_with_long_lines, description="Asking AI to refactor files..."
    ):
        try:
            original_content = file_path.read_text(encoding="utf-8")
            final_prompt = prompt_template.replace("{source_code}", original_content)
            corrected_code = await fixer_client.make_request_async(
                final_prompt, user_id="line_length_fixer_agent"
            )
            if corrected_code and corrected_code.strip() != original_content.strip():
                validation_result = await validate_code_async(
                    str(file_path),
                    corrected_code,
                    quiet=True,
                    auditor_context=auditor_context,
                )
                if validation_result["status"] == "clean":
                    modification_plan[file_path] = validation_result["code"]
                else:
                    logger.warning(
                        f"Skipping {file_path.name}: AI-generated code failed validation."
                    )
        except Exception as e:
            logger.error(f"Could not process {file_path.name}: {e}")
    if dry_run:
        typer.secho("\n💧 Dry Run Summary:", bold=True)
        for file_path in sorted(modification_plan.keys()):
            typer.secho(
                f"  - Would fix line lengths in: {file_path.relative_to(REPO_ROOT)}",
                fg=typer.colors.YELLOW,
            )
    else:
        logger.info("\n💾 Writing changes to disk...")
        for file_path, new_code in modification_plan.items():
            file_path.write_text(new_code, "utf-8")
            logger.info(
                f"   -> ✅ Fixed line lengths in {file_path.relative_to(REPO_ROOT)}"
            )


# ID: 3b56560b-f4d7-4418-9ca8-fd8154744621
def fix_line_lengths(
    context: CoreContext,
    file_path: Path | None = typer.Argument(
        None,
        help="Optional: A specific file to fix. If omitted, all project files are scanned.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--write",
        help="Show what refactoring would be applied. Use --write to apply.",
    ),
):
    """Uses an AI agent to refactor files with lines longer than 100 characters."""
    files_to_scan = []
    if file_path:
        files_to_scan.append(file_path)
    else:
        src_dir = REPO_ROOT / "src"
        files_to_scan.extend(src_dir.rglob("*.py"))
    asyncio.run(
        _async_fix_line_lengths(context.cognitive_service, files_to_scan, dry_run)
    )
