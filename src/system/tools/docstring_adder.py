# src/system/tools/docstring_adder.py
"""
A tool that finds and adds missing docstrings to the codebase, fulfilling
the 'clarity_first' principle. This is a core capability for CORE's
self-healing and self-improvement loop.
"""
import ast
import json
from pathlib import Path

import typer
from rich.progress import track

from core.clients import GeneratorClient
from shared.logger import getLogger

# --- Constants & Setup ---
log = getLogger("docstring_adder")
REPO_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_GRAPH_PATH = REPO_ROOT / ".intent" / "knowledge" / "knowledge_graph.json"


def add_docstring_to_function_line_based(
    source_code: str, line_number: int, docstring: str
) -> str:
    """
    Surgically inserts a docstring into source code using a line-based method.
    This is safer than AST unparsing as it preserves comments and formatting.
    """
    lines = source_code.splitlines()
    target_line_index = line_number - 1
    
    # Determine the indentation from the function definition line
    target_line = lines[target_line_index]
    indentation = len(target_line) - len(target_line.lstrip(' '))
    docstring_indent = ' ' * (indentation + 4) # Standard PEP8 docstring indent

    # Format the docstring
    formatted_docstring = f'{docstring_indent}"""{docstring}"""'

    # Insert the docstring immediately after the function definition line
    lines.insert(target_line_index + 1, formatted_docstring)
    
    return "\n".join(lines)


# CAPABILITY: add_missing_docstrings
def fix_missing_docstrings(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--write",
        help="Show what docstrings would be added without writing any files. Use --write to apply.",
    )
):
    """
    Finds all functions with missing docstrings and uses an LLM to generate them.
    """
    log.info("🩺 Starting self-documentation cycle...")
    generator = GeneratorClient()
    
    kg_data = json.loads(KNOWLEDGE_GRAPH_PATH.read_text())
    symbols = kg_data.get("symbols", {}).values()

    targets = [
        s for s in symbols if not s.get("docstring") and not s.get("is_class")
    ]

    if not targets:
        log.info("✅ No functions with missing docstrings found. The codebase is fully documented.")
        return

    log.info(f"Found {len(targets)} functions requiring docstrings. Generating...")

    for target in track(targets, description="Generating docstrings..."):
        file_path = REPO_ROOT / target["file"]
        func_name = target["name"]
        line_num = target["line_number"]
        log.debug(f"Processing {func_name} in {file_path}...")

        try:
            source_code = file_path.read_text()

            tree = ast.parse(source_code)
            node = next(
                (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func_name),
                None,
            )
            if not node:
                continue

            function_source = ast.unparse(node)

            prompt = (
                f"You are an expert Python programmer specializing in documentation.\n"
                f"Write a clear, concise, single-line docstring for the following function. "
                f"Your response must be ONLY the docstring text itself, without quotes.\n\n"
                f"Function:\n```python\n{function_source}\n```"
            )
            generated_docstring = generator.make_request(prompt).strip().replace('"', "")

            if dry_run:
                typer.secho(f"\n📄 In {file_path.name}, would add to function `{func_name}`:", fg=typer.colors.YELLOW)
                typer.secho(f'   """{generated_docstring}"""', fg=typer.colors.CYAN)
            else:
                new_source_code = add_docstring_to_function_line_based(
                    source_code, line_num, generated_docstring
                )
                file_path.write_text(new_source_code)
                typer.secho(f"   -> ✅ Added docstring to `{func_name}` in {file_path.name}", fg=typer.colors.GREEN)

        except Exception as e:
            log.error(f"   -> ❌ Failed to process `{func_name}` in {file_path.name}: {e}")

    log.info("\n🎉 Self-documentation cycle complete.")


if __name__ == "__main__":
    typer.run(fix_missing_docstrings)
