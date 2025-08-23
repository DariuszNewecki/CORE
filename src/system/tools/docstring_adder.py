# src/system/tools/docstring_adder.py
"""
A tool that finds and adds missing docstrings to the codebase, fulfilling
the 'clarity_first' principle. This is a core capability for CORE's
self-healing and self-improvement loop.
"""
import ast
import asyncio
import json
from typing import Any, Dict

import typer
from rich.progress import track

from core.cognitive_service import CognitiveService
from core.validation_pipeline import validate_code
from shared.logger import getLogger
from shared.path_utils import get_repo_root
from system.tools.codegraph_builder import KnowledgeGraphBuilder

# --- Constants & Setup ---
log = getLogger("docstring_adder")
REPO_ROOT = get_repo_root()
KNOWLEDGE_GRAPH_PATH = REPO_ROOT / ".intent" / "knowledge" / "knowledge_graph.json"
CONCURRENCY_LIMIT = 10


def add_docstring_to_function_line_based(
    source_code: str, line_number: int, docstring: str
) -> str:
    """Surgically inserts a docstring into source code using a line-based method."""
    lines = source_code.splitlines()
    if not lines or line_number < 1 or line_number > len(lines):
        log.error(f"Invalid line number {line_number} for source code")
        return source_code

    target_line_index = line_number - 1
    target_line = lines[target_line_index]
    indentation = len(target_line) - len(target_line.lstrip())
    docstring_indent = " " * (indentation + 4)

    # Sanitize the docstring to prevent breaking the code structure
    docstring = docstring.strip().replace('"""', "'")
    if not docstring:
        log.warning("Empty docstring received")
        return source_code

    formatted_docstring = f'{docstring_indent}"""{docstring}"""'

    if target_line_index + 1 < len(lines) and '"""' in lines[target_line_index + 1]:
        log.warning(f"Docstring already exists at line {line_number}")
        return source_code

    lines.insert(target_line_index + 1, formatted_docstring)
    return "\n".join(lines)


async def generate_and_apply_docstring(
    target: Dict[str, Any], cognitive_service: CognitiveService, dry_run: bool
) -> None:
    """Generates, validates, and applies a docstring for a single symbol."""
    func_name = target.get("name")

    file_rel_path = target.get("file")
    if not isinstance(file_rel_path, str):
        return

    file_path = REPO_ROOT / file_rel_path
    line_num = target.get("line_number")

    try:
        if not file_path.exists():
            return

        source_code = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)

        node_to_update = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
                and node.name == func_name
                and node.lineno == line_num
            ),
            None,
        )

        if not node_to_update or ast.get_docstring(node_to_update):
            return

        doc_writer_client = cognitive_service.get_client_for_role("DocstringWriter")
        function_source = ast.unparse(node_to_update)
        prompt = (
            f"You are an expert Python programmer specializing in documentation.\n"
            f"Write a clear, concise, single-line docstring for the following symbol. "
            f"Your response must be ONLY the docstring text itself, without quotes.\n\n"
            f"Symbol:\n```python\n{function_source}\n```"
        )

        generated_docstring = await doc_writer_client.make_request_async(
            prompt, user_id="docstring_adder"
        )
        if "Error:" in generated_docstring:
            return

        new_source_code = add_docstring_to_function_line_based(
            source_code, line_num, generated_docstring
        )
        validation_result = validate_code(str(file_path), new_source_code, quiet=True)
        if validation_result["status"] == "dirty":
            return

        if dry_run:
            typer.secho(
                f"\n📄 In {file_path.name}, would add to function `{func_name}`:",
                fg=typer.colors.YELLOW,
            )
            typer.secho(f'   """{generated_docstring.strip()}"""', fg=typer.colors.CYAN)
        elif validation_result["code"] != source_code:
            file_path.write_text(validation_result["code"], encoding="utf-8")
            log.info(f"Added docstring to `{func_name}` in {file_path.name}")

    except Exception as e:
        log.error(f"Failed to process `{func_name}` in {file_path}: {e}", exc_info=True)


async def _async_main(dry_run: bool):
    """The core asynchronous logic for finding and fixing docstrings."""
    log.info("🩺 Starting self-documentation cycle...")

    builder = KnowledgeGraphBuilder(REPO_ROOT)
    graph = builder.build()
    KNOWLEDGE_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    cognitive_service = CognitiveService(REPO_ROOT)
    symbols = graph.get("symbols", {}).values()
    targets = [
        s
        for s in symbols
        if not s.get("docstring")
        and s.get("type") in ["FunctionDef", "AsyncFunctionDef", "ClassDef"]
    ]

    if not targets:
        log.info("✅ No symbols with missing docstrings found.")
        return

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def worker(target):
        """Asynchronously processes a target by acquiring a semaphore, then generating and applying a docstring using a cognitive service."""
        async with semaphore:
            await generate_and_apply_docstring(target, cognitive_service, dry_run)

    tasks = [worker(target) for target in targets]
    for f in track(
        asyncio.as_completed(tasks),
        description="Generating docstrings...",
        total=len(tasks),
    ):
        await f

    log.info("🎉 Self-documentation cycle complete.")


# CAPABILITY: add_missing_docstrings
def fix_missing_docstrings(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--write",
        help="Show what docstrings would be added without writing any files. Use --write to apply.",
    )
):
    """Finds all symbols with missing docstrings and uses an LLM to generate and apply them, with validation."""
    asyncio.run(_async_main(dry_run))

    if not dry_run:
        log.info("🧠 Rebuilding knowledge graph to reflect changes...")
        builder = KnowledgeGraphBuilder(REPO_ROOT)
        graph = builder.build()
        out_path = REPO_ROOT / ".intent/knowledge/knowledge_graph.json"
        out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        log.info("✅ Knowledge graph successfully updated.")


if __name__ == "__main__":
    typer.run(fix_missing_docstrings)
