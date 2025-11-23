# src/features/self_healing/docstring_service.py

"""
Implements the 'fix docstrings' command, an AI-powered tool to add
missing docstrings to functions and methods.
"""

from __future__ import annotations

from rich.progress import track

from features.introspection.knowledge_helpers import extract_source_code
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


async def _async_fix_docstrings(context: CoreContext, dry_run: bool):
    """Async core logic for finding and fixing missing docstrings."""
    logger.info("🔍 Searching for symbols missing docstrings...")
    knowledge_service = context.knowledge_service
    graph = await knowledge_service.get_graph()
    symbols = graph.get("symbols", {})
    symbols_to_fix = [
        s
        for s in symbols.values()
        if not s.get("docstring")
        and s.get("type") in ["FunctionDef", "AsyncFunctionDef"]
    ]
    if not symbols_to_fix:
        logger.info("✅ No symbols are missing docstrings. Excellent!")
        return
    logger.info(f"Found {len(symbols_to_fix)} symbol(s) missing docstrings. Fixing...")
    cognitive_service = context.cognitive_service
    prompt_template = (
        settings.MIND / "prompts" / "fix_function_docstring.prompt"
    ).read_text(encoding="utf-8")
    writer_client = await cognitive_service.aget_client_for_role("DocstringWriter")
    modification_plan = {}
    for symbol in track(symbols_to_fix, description="Generating docstrings..."):
        try:
            source_code = extract_source_code(REPO_ROOT, symbol)
            final_prompt = prompt_template.format(source_code=source_code)
            new_docstring_content = await writer_client.make_request_async(
                final_prompt, user_id="docstring_writer_agent"
            )
            if new_docstring_content:
                file_path = REPO_ROOT / symbol["file_path"]
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
            logger.error(f"Could not process {symbol['symbol_path']}: {e}")
    if dry_run:
        from typer import secho

        secho("\n💧 Dry Run Summary:", bold=True)
        for file_path, patches in modification_plan.items():
            secho(
                f"  - Would add {len(patches)} docstring(s) to: {file_path.relative_to(REPO_ROOT)}",
                fg="yellow",
            )
    else:
        logger.info("\n💾 Writing changes to disk...")
        for file_path, patches in modification_plan.items():
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
                patches.sort(key=lambda p: p["line_number"], reverse=True)
                for patch in patches:
                    indent_space = " " * (patch["indent"] + 4)
                    docstring = f'{indent_space}"""{patch['docstring']}"""'
                    lines.insert(patch["line_number"], docstring)
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                logger.info(
                    f"   -> ✅ Wrote {len(patches)} docstring(s) to {file_path.relative_to(REPO_ROOT)}"
                )
            except Exception as e:
                logger.error(f"Failed to write to {file_path}: {e}")


# --- START OF FIX: Convert the main function to async and await the core logic ---
# ID: 43c3af5c-b9e3-4f5a-a95d-3b8945a71567
async def fix_docstrings(context: CoreContext, write: bool):
    """Uses an AI agent to find and add missing docstrings to functions and methods."""
    await _async_fix_docstrings(context, dry_run=not write)


# --- END OF FIX ---
