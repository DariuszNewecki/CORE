# src/cli/resources/promote/propose.py
"""``core-admin promote propose`` — open or update the promotion pull request.

Run once a day by core-promote-propose.timer (infra/core-one-path-setup) and
by hand for an urgent promotion (``--urgent``): it proposes main's newest
green commit since ``live`` and names the high-risk changes first. The token
comes from ``CORE_GITHUB_TOKEN`` or the unit's credential ``github-token``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console

from body.services.promotion import (
    GitHubUnavailable,
    build_proposal,
    live_commit,
    publish,
)
from body.services.thesis.github import GitHub
from cli.utils import async_command
from shared.config import settings
from will.audit_violation.governor_alarms import open_alarms

from .hub import app


console = Console()

GITHUB_REPO = "DariuszNewecki/CORE"
PIPELINE_STATUS = Path("/var/lib/core-pipeline/status.json")


def _token() -> str | None:
    if settings.CORE_GITHUB_TOKEN:
        return settings.CORE_GITHUB_TOKEN
    creds = os.environ.get("CREDENTIALS_DIRECTORY")
    path = Path(creds) / "github-token" if creds else None
    if path and path.is_file():
        return path.read_text(encoding="utf-8").strip() or None
    return None


def _pipeline(status_file: Path) -> dict[str, Any] | None:
    try:
        return json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@app.command("propose")
@async_command
# ID: 306f7e0f-0af6-44f7-8585-58d08a820b6b
async def propose_cmd(
    urgent: bool = typer.Option(
        False, "--urgent", help="Propose main now, outside the daily schedule."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the proposal; change nothing on GitHub."
    ),
    repo: str = typer.Option(GITHUB_REPO, "--repo", help="The GitHub repository."),
    status_file: Path = typer.Option(
        PIPELINE_STATUS,
        "--status-file",
        help="core-pipeline's status: the live commit and the last sandbox check.",
    ),
) -> None:
    """Propose main's newest green commit for promotion to live."""
    token = _token()
    if not token and not dry_run:
        console.print(
            "[red]A promotion needs a GitHub token (CORE_GITHUB_TOKEN).[/red]"
        )
        raise typer.Exit(1)
    pipeline = _pipeline(status_file)
    alarms = await open_alarms()
    for alarm in alarms:
        console.print(f"[red]Needs the governor:[/red] {alarm}")
    async with httpx.AsyncClient() as client:
        gh = GitHub(repo, token, client)
        try:
            live, note = await live_commit(gh, pipeline)
            if not live:
                console.print(
                    "[red]No live commit known (no status, no live branch).[/red]"
                )
                raise typer.Exit(1)
            if note:
                console.print(f"[yellow]{note}[/yellow]")
            proposal = await build_proposal(
                gh, live, pipeline, urgent=urgent, note=note, alarms=alarms
            )
            if proposal is None:
                console.print(
                    f"Nothing to promote: main has no new green commit since {str(live)[:12]}."
                )
                return
            if dry_run:
                console.print(proposal.title())
                console.print(proposal.body())
                return
            url = await publish(gh, proposal)
        except GitHubUnavailable as exc:
            console.print(f"[red]GitHub: {exc}[/red]")
            raise typer.Exit(1) from exc
    console.print(f"{proposal.title()}: {url}")
