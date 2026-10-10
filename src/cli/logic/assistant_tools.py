# src/cli/logic/assistant_tools.py

"""The assistant surface's tools: one allowlist behind every face (ADR-168 D3, D4.3).

The CLI commands (``law``, ``decisions``, ``code verify``) and the MCP server
call ``invoke`` with the same name and arguments, so every face gives the same
answer from the same code. This is the parity half of the D2 amendment
(2026-10-06): one shared core, thin faces.

The allowlist is explicit. Nothing here reflects routes, registries or CLI
commands. The read tools are read-only: no database, no LLM, no writes.

ADR-168 Amendment 2026-10-10 A1 adds exactly one write: submitting a change
as a proposal, in two steps so the full check (minutes) never outlives a tool
call. ``validate_change`` asks CORE to check a patch in general mode;
``submit_change`` reads that run and, if it passed, asks CORE to create a
PENDING proposal. Both reach CORE only over its API (CORE does the writing,
as itself) and only on the routes in ``_SUBMIT_ROUTES``. None approves,
rejects or executes; none can record governor authority (D3).
"""

from __future__ import annotations

import getpass
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.cli.client import CoreApiClient
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


# Every API call the submit tools make: (method, path prefix). A test holds
# the tools to this list (ADR-168 D3 authority enumeration).
_SUBMIT_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/v1/fix/run/assisted.validate_diff"),
    ("GET", "/v1/fix/runs/"),
    ("POST", "/v1/proposals/submit"),
)


async def _validate_change(
    repo_root: Path, arguments: dict[str, Any]
) -> dict[str, Any]:
    patch = _text(arguments, "patch")
    dispatched = await CoreApiClient()._request(
        "POST",
        "/v1/fix/run/assisted.validate_diff",
        json={
            "target_files": [],
            "write": False,
            "params": {"patch": patch, "general": True},
        },
    )
    return {
        "validation_run_id": dispatched.get("run_id"),
        "status": dispatched.get("status", "pending"),
        "next": "call submit_change with this validation_run_id once it has completed "
        "(a full check takes a few minutes)",
    }


async def _submit_change(repo_root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    run_id = _text(arguments, "validation_run_id")
    refs = arguments.get("anchor_refs")
    if (
        not isinstance(refs, list)
        or not all(isinstance(r, str) for r in refs)
        or not refs
    ):
        raise ToolInputError("'anchor_refs' must be a non-empty list of strings.")
    retires = arguments.get("retires") or []
    if not isinstance(retires, list) or not all(isinstance(r, str) for r in retires):
        raise ToolInputError("'retires' must be a list of strings when given.")
    client = CoreApiClient()
    run = await client._request("GET", f"/v1/fix/runs/{run_id}")
    status = run.get("status")
    if status not in ("completed", "failed"):
        return {
            "submitted": False,
            "validation_status": status,
            "next": "wait and call again",
        }
    result = run.get("result") or {}
    if status != "completed" or not result.get("ok"):
        data = result.get("data") or {}
        return {
            "submitted": False,
            "validation_status": status,
            "reason": "the change did not pass CORE's checks; nothing was submitted",
            "validation_results": data.get("validation_results"),
            "blocking_findings": data.get("blocking_findings"),
            "class_b": data.get("class_b"),
            "error": data.get("error") or result.get("error"),
        }
    # The producer as claimed, plus the account that actually ran this tool.
    producer = f"{_text(arguments, 'producer')} (account: {getpass.getuser()})"
    proposal = await client._request(
        "POST",
        "/v1/proposals/submit",
        json={
            "patch": _text(arguments, "patch"),
            "validation_run_id": run_id,
            "goal": _text(arguments, "goal"),
            "anchor_kind": _text(arguments, "anchor_kind"),
            "anchor_refs": refs,
            "producer": producer,
            "retires": retires,
        },
    )
    return {"submitted": True, **proposal}


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
        AssistantTool(
            name="validate_change",
            description=(
                "Step 1 of submitting a change (ADR-168 Amendment 2026-10-10 A1): ask "
                "CORE to check a unified diff in full (governed-text refusal, full "
                "blocking audit, test rules, tests). Returns a validation_run_id at "
                "once; the check takes a few minutes. Writes nothing to the tree."
            ),
            input_schema={
                "type": "object",
                "properties": {"patch": _STRING},
                "required": ["patch"],
                "additionalProperties": False,
            },
            handler=_validate_change,
        ),
        AssistantTool(
            name="submit_change",
            description=(
                "Step 2: if the validation run passed, CORE creates a PENDING proposal "
                "for the same patch, with its anchor (issue | adr | governor_request), "
                "producer and what it retires, and answers step 0. Approval is always "
                "the governor's, typed at a terminal; this tool never approves. If "
                "the run is still going or failed, says so and submits nothing."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "patch": _STRING,
                    "validation_run_id": _STRING,
                    "goal": _STRING,
                    "anchor_kind": {
                        "type": "string",
                        "enum": ["issue", "adr", "governor_request"],
                    },
                    "anchor_refs": {"type": "array", "items": _STRING},
                    "producer": _STRING,
                    "retires": {"type": "array", "items": _STRING},
                },
                "required": [
                    "patch",
                    "validation_run_id",
                    "goal",
                    "anchor_kind",
                    "anchor_refs",
                    "producer",
                ],
                "additionalProperties": False,
            },
            handler=_submit_change,
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
