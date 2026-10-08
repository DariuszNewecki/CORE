# src/cli/utils/assistant_output.py

"""CLI face of the assistant surface (ADR-168 D4.3 unit 3).

Each ``law`` / ``decisions`` / ``code verify`` command runs one allowlisted
tool through ``cli.logic.assistant_tools.invoke`` — the same call the MCP
server makes — and prints the answer as JSON, unchanged, so both faces give
identical answers.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from cli.logic.assistant_tools import ToolInputError, invoke
from cli.utils.exit_codes import EXIT_CONFIG_ERROR
from shared.path_utils import get_repo_root


# ID: dd03eea9-37b1-44c2-8730-edc3c52e012a
async def run_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run tool ``name`` for the repository around the working directory and
    print its answer as JSON. Bad input or no repository exits with code 2."""
    try:
        result = await invoke(name, arguments, get_repo_root())
    except (ToolInputError, FileNotFoundError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    return result
