# src/cli/logic/mcp_server.py

"""The assistant surface's MCP face: a local stdio server (ADR-168 D4.3 unit 4).

Started by the assistant (``core-admin mcp run``) in the repository it works
on. It lists exactly the allowlisted tools of ``cli.logic.assistant_tools``
and answers each call through the same ``invoke`` the CLI commands use, so the
MCP and CLI answers are identical (D2 amendment 2026-10-06).

Local first: no database, no API, no other service. Every tool is read-only,
and none can record governor authority (D3). The SDK's stdio transport points
fd 1 at stderr while serving, so CORE's logging never reaches the protocol.
"""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from typing import Any

import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server

from cli.logic.assistant_tools import TOOLS, ToolInputError, invoke
from shared.logger import getLogger


logger = getLogger(__name__)

SERVER_NAME = "core"

_INSTRUCTIONS = (
    "CORE governs this repository. Ask it before you guess: law_rule and "
    "law_can_write answer from the repository's law, decision_adr and "
    "decision_adrs from its decision history, each with its sources and its "
    "limits. Before committing, call change_verdict on your change: BLOCKED "
    "means a blocking rule is violated; CLEAR_IN_SCOPE means none of the rules "
    "it evaluated is, and it names the rules it did not evaluate. It never says "
    "PASS; the full audit (commit hook, CI) is authoritative. These tools only "
    "read: none can approve, waive or act as the governor."
)

# Every tool only reads the repository; none reaches outside it.
_READ_ONLY = types.ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def _version() -> str:
    try:
        return importlib.metadata.version("core-runtime")
    except importlib.metadata.PackageNotFoundError:
        return ""


# ID: 215862ea-1de4-485f-b3d4-78d756c11e7b
def build_server(repo_root: Path) -> Server[Any]:
    """An MCP server over the allowlisted tools, bound to ``repo_root``."""
    root = Path(repo_root).resolve()

    async def _list_tools(
        ctx: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    annotations=_READ_ONLY,
                )
                for tool in TOOLS.values()
            ]
        )

    async def _call_tool(
        ctx: ServerRequestContext[Any], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        try:
            result = await invoke(params.name, params.arguments, root)
        except ToolInputError as exc:
            # Reported inside the result so the assistant can correct its call.
            return types.CallToolResult(
                content=[types.TextContent(text=str(exc))], is_error=True
            )
        return types.CallToolResult(
            content=[types.TextContent(text=json.dumps(result, ensure_ascii=False))],
            structured_content=result,
        )

    return Server(
        SERVER_NAME,
        version=_version(),
        instructions=_INSTRUCTIONS,
        on_list_tools=_list_tools,
        on_call_tool=_call_tool,
    )


# ID: b9579c86-6d11-406f-bfa6-105b9e82d0bd
async def serve_stdio(repo_root: Path) -> None:
    """Serve the assistant surface over stdin/stdout until the client closes."""
    server = build_server(repo_root)
    logger.info("MCP assistant surface serving %s over stdio", repo_root)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )
