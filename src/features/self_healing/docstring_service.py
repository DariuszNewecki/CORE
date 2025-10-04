# src/features/self_healing/docstring_service.py
"""
Implements the 'fix docstrings' command, an AI-powered tool to add
missing docstrings to functions and methods.
"""

from __future__ import annotations

import asyncio

import typer
from core.cognitive_service import CognitiveService
from core.knowledge_service import KnowledgeService
from rich.progress import track
from shared.config import settings
from shared.logger import getLogger

from features.introspection.knowledge_helpers import extract_source_code

log = getLogger("core_admin.fixer_docstrings")
REPO_ROOT = settings.REPO_PATH


async def _async_fix_docstrings(dry_run: bool):
    """Async core logic for finding and fixing missing docstrings."""
    log.info("🔍 Searching for symbols missing docstrings...")

    knowledge_service = KnowledgeService(REPO_ROOT)
    graph = await knowledge_service.get_graph()
    symbols = graph.get("symbols", {})

    symbols_to_fix = [
        s
        for s in symbols.values()
        if not s.get("docstring")
        and s.get("type") in ["FunctionDef", "AsyncFunctionDef"]
    ]

    if not symbols_to_fix:
        log.info("✅ No symbols are missing docstrings. Excellent!")
        return

    log.info(f"Found {len(symbols_to_fix)} symbol(s) missing docstrings. Fixing...")

    cognitive_service = CognitiveService(REPO_ROOT)
    prompt_template = (
        settings.MIND / "prompts" / "fix_function_docstring.prompt"
    ).read_text(encoding="utf-8")
    writer_client = cognitive_service.get_client_for_role("DocstringWriter")

    modification_plan = {}

    for symbol in track(symbols_to_fix, description="Generating docstrings..."):
        try:
            source_code = extract_source_code(REPO_ROOT, symbol)
            final_prompt = prompt_template.format(source_code=source_code)

            new_docstring_content = await writer_client.make_request_async(
                final_prompt, user_id="docstring_writer_agent"
            )

            if new_docstring_content:
                file_path = REPO_ROOT / symbol["file"]
                if file_path not in modification_plan:
                    modification_plan[file_path] = []

                modification_plan[file_path].append(
                    {
                        "line_number": symbol["line_number"],
                        "indent": len(symbol.get("name", ""))
                        - len(symbol.get("name", "").lstrip()),
                        "docstring": new_docstring_content.strip().replace('"', '\\"'),
                    }
                )

        except Exception as e:
            log.error(f"Could not process {symbol['symbol_path']}: {e}")

    if dry_run:
        typer.secho("\n💧 Dry Run Summary:", bold=True)
        for file_path, patches in modification_plan.items():
            typer.secho(
                f"  - Would add {len(patches)} docstring(s) to: "
                f"{file_path.relative_to(REPO_ROOT)}",
                fg=typer.colors.YELLOW,
            )
    else:
        log.info("\n💾 Writing changes to disk...")
        for file_path, patches in modification_plan.items():
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
                patches.sort(key=lambda p: p["line_number"], reverse=True)

                for patch in patches:
                    indent_space = " " * (patch["indent"] + 4)
                    docstring = f'{indent_space}"""{patch["docstring"]}"""'
                    lines.insert(patch["line_number"], docstring)

                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                log.info(
                    f"   -> ✅ Wrote {len(patches)} docstring(s) to "
                    f"{file_path.relative_to(REPO_ROOT)}"
                )
            except Exception as e:
                log.error(f"Failed to write to {file_path}: {e}")


# ID: 974fbc4d-da2e-4f45-8199-30972715c284
def fix_docstrings(
    write: bool = typer.Option(
        False, "--write", help="Apply the suggested docstrings directly to the files."
    ),
):
    """Uses an AI agent to find and add missing docstrings to functions and methods."""
    asyncio.run(_async_fix_docstrings(dry_run=not write))
