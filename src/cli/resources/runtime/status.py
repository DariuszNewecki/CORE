# src/cli/resources/runtime/status.py
"""
``core-admin runtime status`` — one screen: last merge, what is live, what
waits on the governor (one-path flow, governor ruling 2026-10-12).

Reads the post-merge runner's status file (written by core-pipeline as
core-runner, world-readable), GitHub's open pull requests into main, and
CORE's own API for what needs the governor. Read-only; any source that cannot
be reached is shown as unavailable, never guessed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from cli.utils import async_command

from .health import runtime_app


console = Console()

PIPELINE_STATUS = Path("/var/lib/core-pipeline/status.json")
GITHUB_REPO = "DariuszNewecki/CORE"
API = "http://127.0.0.1:8000"


async def _get(client: httpx.AsyncClient, url: str) -> Any:
    try:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _short(sha: object) -> str:
    return str(sha)[:12] if sha else "-"


@runtime_app.command("status")
@async_command
# ID: 3bfc24c0-725d-4389-8603-68920c3bce58
async def status_cmd(
    status_file: Path = typer.Option(PIPELINE_STATUS, "--status-file"),
    repo: str = typer.Option(GITHUB_REPO, "--repo"),
    api: str = typer.Option(API, "--api"),
) -> None:
    """Last merge, what applied and deployed, and what waits on the governor."""
    pipeline: dict[str, Any] = {}
    if status_file.is_file():
        pipeline = json.loads(status_file.read_text(encoding="utf-8"))
    async with httpx.AsyncClient() as client:
        prs = await _get(
            client, f"https://api.github.com/repos/{repo}/pulls?base=main&state=open"
        )
        proposals = await _get(client, f"{api}/v1/proposals?limit=500")
        lane = await _get(client, f"{api}/v1/lane?limit=10000")

    last = pipeline.get("last") or {}
    table = Table(title="CORE status", show_header=False)
    table.add_column("what")
    table.add_column("state")
    table.add_row("live commit", _short(pipeline.get("live")))
    table.add_row("main", _short(pipeline.get("main_head")))
    table.add_row("runner", str(pipeline.get("state", "no status file")))
    if last:
        detail = last.get("what") or ""
        table.add_row(
            "last merge",
            f"{_short(last.get('sha'))} {last.get('result', '')} {detail}".strip(),
        )
        if last.get("issue"):
            table.add_row("issue", str(last["issue"]))
    table.add_section()
    table.add_row(
        "PRs waiting for your merge",
        str(len(prs)) if isinstance(prs, list) else "unavailable",
    )
    table.add_row(
        "proposals waiting for you",
        str(proposals.get("count", 0))
        if isinstance(proposals, dict)
        else "unavailable",
    )
    table.add_row(
        "findings waiting for you",
        str(lane.get("count", 0)) if isinstance(lane, dict) else "unavailable",
    )
    console.print(table)
    if isinstance(prs, list):
        for pr in prs[:10]:
            console.print(f"  #{pr.get('number')} {pr.get('title')}")
