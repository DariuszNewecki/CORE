# src/cli/logic/assistant_tools.py

"""The assistant surface's tools: one allowlist behind every face (ADR-168 D3, D4.3).

The CLI commands (``law``, ``decisions``, ``code verify``) and the MCP server
call ``invoke`` with the same name and arguments, so every face gives the same
answer from the same code. This is the parity half of the D2 amendment
(2026-10-06): one shared core, thin faces.

The allowlist is explicit. Nothing here reflects routes, registries or CLI
commands. Every tool is read-only: no database, no LLM, no writes. None can
record governor authority (ADR-168 D3: until #942 is resolved, the surface
exposes no operation whose result is represented as a governor act).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mind.governance.fast_verdict import run_fast_verdict
from shared.infrastructure.assistant_surface.law_facts import LawFacts
from shared.infrastructure.intent.intent_repository import IntentRepository


Handler = Callable[[Path, dict[str, Any]], Awaitable[dict[str, Any]]]


# ID: f3cc4ff6-ee95-4367-982f-e175134f0b38
class ToolInputError(ValueError):
    """A tool was called with missing or invalid arguments."""


@dataclass(frozen=True)
# ID: e9ead535-b4fd-4a7a-a4c5-704fbd14f487
class AssistantTool:
    """One allowlisted, read-only operation, with the JSON Schema of its input."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler


def _text(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"'{key}' is required and must be a non-empty string.")
    return value.strip()


async def _law_rule(repo_root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    return LawFacts(repo_root).rule(_text(arguments, "rule_id")).as_dict()


async def _law_can_write(repo_root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    return LawFacts(repo_root).can_write(_text(arguments, "path")).as_dict()


async def _decision_adr(repo_root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    return LawFacts(repo_root).adr(_text(arguments, "adr_id")).as_dict()


async def _decision_adrs(repo_root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    status = arguments.get("status")
    if status is not None and not isinstance(status, str):
        raise ToolInputError("'status' must be a string when given.")
    return LawFacts(repo_root).adrs(status=status or None).as_dict()


async def _change_verdict(repo_root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    files = arguments.get("files")
    if files is not None:
        if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
            raise ToolInputError("'files' must be a list of paths when given.")
        files = [_inside(repo_root, f) for f in files]
    intent_repo = IntentRepository(strict=True, root=repo_root / ".intent")
    intent_repo.initialize()
    return await run_fast_verdict(intent_repo, repo_root, files=files or None)


def _inside(repo_root: Path, path: str) -> str:
    """Repository-relative form of ``path``; refuses a path outside the root."""
    root = repo_root.resolve()
    candidate = Path(path)
    absolute = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        return absolute.relative_to(root).as_posix()
    except ValueError as exc:
        raise ToolInputError(f"'{path}' is outside this repository.") from exc


_STRING = {"type": "string"}

TOOLS: dict[str, AssistantTool] = {
    tool.name: tool
    for tool in (
        AssistantTool(
            name="law_rule",
            description=(
                "What a CORE rule says: statement, enforcement level, authority, "
                "and the mechanism that enforces it, with source files."
            ),
            input_schema={
                "type": "object",
                "properties": {"rule_id": _STRING},
                "required": ["rule_id"],
                "additionalProperties": False,
            },
            handler=_law_rule,
        ),
        AssistantTool(
            name="law_can_write",
            description=(
                "May a producer write this path? Answers what the law says and, "
                "separately, what actually enforces it; never one word."
            ),
            input_schema={
                "type": "object",
                "properties": {"path": _STRING},
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_law_can_write,
        ),
        AssistantTool(
            name="decision_adr",
            description=(
                "One architecture decision record (ADR): id, title, status and its "
                "decision headings, with its file. Accepts 'ADR-168' or '168'."
            ),
            input_schema={
                "type": "object",
                "properties": {"adr_id": _STRING},
                "required": ["adr_id"],
                "additionalProperties": False,
            },
            handler=_decision_adr,
        ),
        AssistantTool(
            name="decision_adrs",
            description=(
                "Every ADR's id, title and status; optionally only those whose "
                "status begins with the given text (for example 'accepted')."
            ),
            input_schema={
                "type": "object",
                "properties": {"status": _STRING},
                "additionalProperties": False,
            },
            handler=_decision_adrs,
        ),
        AssistantTool(
            name="change_verdict",
            description=(
                "Fast verdict on the current change (every path that differs from "
                "HEAD, or the given files): BLOCKED, CLEAR_IN_SCOPE, NO_CHANGES or "
                "NOT_EVALUATED (nothing could be judged; see 'error'), naming every "
                "rule it did not evaluate. Producer feedback, never "
                "PASS: the full audit (commit hook, CI) stays authoritative."
            ),
            input_schema={
                "type": "object",
                "properties": {"files": {"type": "array", "items": _STRING}},
                "additionalProperties": False,
            },
            handler=_change_verdict,
        ),
    )
}


# ID: a2643b7e-8f1f-4fb0-a1d6-badb189e4d01
async def invoke(
    name: str, arguments: dict[str, Any] | None, repo_root: Path
) -> dict[str, Any]:
    """Run allowlisted tool ``name`` against ``repo_root``. Raises
    ``ToolInputError`` for an unknown tool or invalid arguments."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolInputError(f"No assistant tool named {name!r}.")
    return await tool.handler(Path(repo_root).resolve(), dict(arguments or {}))
