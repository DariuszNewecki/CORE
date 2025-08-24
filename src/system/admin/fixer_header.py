# src/system/admin/fixer_header.py
"""
The orchestration logic for the unified header fixer.
"""
from __future__ import annotations

import asyncio
from typing import Dict

import typer
from rich.progress import track

from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger
from shared.path_utils import get_repo_root
from system.tools.header_tools import HeaderTools

log = getLogger("core_admin.fixer")
REPO_ROOT = get_repo_root()
CONCURRENCY_LIMIT = 5


async def _run_header_fix_cycle(dry_run: bool, all_py_files: list[str]):
    """The core async logic for finding and fixing all header style violations."""
    # THIS IS THE FIX: The service is now created inside the function.
    cognitive_service = CognitiveService(REPO_ROOT)
    modification_plan: Dict[str, str] = {}

    async def worker(file_path_str: str):
        file_path = REPO_ROOT / file_path_str
        try:
            content = file_path.read_text(encoding="utf-8")
            header = HeaderTools.parse(content)

            is_compliant = (
                header.location is not None
                and header.module_description is not None
                and header.has_future_import
            )
            if is_compliant:
                return

            header.location = f"# {file_path_str.replace('\\', '/')}"
            header.has_future_import = True

            if not header.module_description:
                prompt_template = (
                    settings.MIND / "prompts" / "module_docstring_writer.prompt"
                ).read_text(encoding="utf-8")
                final_prompt = prompt_template.replace("{source_code}", content)
                doc_writer = cognitive_service.get_client_for_role("DocstringWriter")
                docstring_text = await doc_writer.make_request_async(
                    final_prompt, user_id="header_fixer"
                )
                if "Error:" not in docstring_text:
                    header.module_description = f'"""\n{docstring_text.strip()}\n"""'

            new_content = HeaderTools.reconstruct(header)
            if new_content != content:
                modification_plan[file_path_str] = new_content

        except Exception as e:
            log.warning(f"Could not process {file_path_str}: {e}")

    tasks = [worker(file_path) for file_path in all_py_files]
    for task in track(
        asyncio.as_completed(tasks), "Analyzing headers...", total=len(tasks)
    ):
        await task

    if not modification_plan:
        log.info("✅ All file headers are constitutionally compliant.")
        return

    log.info(f"Found {len(modification_plan)} file(s) requiring header fixes.")

    if dry_run:
        typer.secho("💧 Dry Run Summary:", bold=True)
        for file_path in sorted(modification_plan.keys()):
            typer.secho(f"  - Would fix header in: {file_path}", fg=typer.colors.YELLOW)
        return

    log.info("💾 Validating and writing changes to disk...")
    # (The rest of the logic remains the same)
    from core.validation_pipeline import validate_code

    for file_path, new_code in track(modification_plan.items(), "Applying fixes..."):
        validation_result = validate_code(file_path, new_code, quiet=True)
        if validation_result["status"] == "clean":
            (REPO_ROOT / file_path).write_text(validation_result["code"], "utf-8")
        else:
            log.error(f"❌ Skipping {file_path} due to validation failure after fix.")
