"""ADR-168 D4.3 unit 4: the MCP face of the assistant surface.

On the same adopter-shaped repository as the CLI-face tests:

- the server lists exactly the allowlisted tools, each annotated read-only;
- every MCP call returns exactly the shared tool's answer (CLI ≡ MCP parity,
  since the CLI test pins CLI ≡ tool);
- an unknown tool or bad arguments come back as a tool error, never a crash;
- the real ``core-admin mcp run`` program, spoken to over stdio by a real MCP
  client, answers — so nothing CORE prints or logs corrupts the protocol.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cli.logic.assistant_tools import TOOLS, invoke
from cli.logic.mcp_server import build_server
from tests.cli.logic import test_assistant_tools as _shared


# The adopter-shaped repository and the per-tool calls of the CLI-face tests.
repo = _shared.repo
_CALLS = _shared._CALLS


@pytest.mark.asyncio
async def test_lists_exactly_the_allowlisted_tools_as_read_only(repo: Path) -> None:
    async with Client(build_server(repo)) as client:
        listed = (await client.list_tools()).tools

    assert [t.name for t in listed] == list(TOOLS)
    for tool in listed:
        assert tool.input_schema == TOOLS[tool.name].input_schema
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False


@pytest.mark.asyncio
async def test_every_call_answers_exactly_what_the_shared_tool_answers(
    repo: Path,
) -> None:
    async with Client(build_server(repo)) as client:
        for name, arguments in _CALLS.items():
            result = await client.call_tool(name, arguments)
            assert result.is_error is False, name
            assert result.structured_content == await invoke(name, arguments, repo)


@pytest.mark.asyncio
async def test_unknown_tool_and_bad_arguments_are_tool_errors(repo: Path) -> None:
    async with Client(build_server(repo)) as client:
        unknown = await client.call_tool("governor_approve", {})
        missing = await client.call_tool("law_rule", {})

    assert unknown.is_error is True
    assert "No assistant tool" in unknown.content[0].text
    assert missing.is_error is True
    assert "rule_id" in missing.content[0].text


@pytest.mark.asyncio
async def test_core_admin_mcp_run_serves_over_stdio(repo: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cli.admin_cli", "mcp", "run"],
        cwd=repo,
    )
    arguments = _CALLS["law_can_write"]

    async with Client(params, read_timeout_seconds=120) as client:
        listed = (await client.list_tools()).tools
        result = await client.call_tool("law_can_write", arguments)

    assert [t.name for t in listed] == list(TOOLS)
    assert result.structured_content == await invoke("law_can_write", arguments, repo)
