# src/cli/resources/lane/next.py
"""`core-admin lane next` — pull the next delegated finding to work."""

from __future__ import annotations

import logging

import httpx
from rich.console import Console
from rich.panel import Panel

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)

console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 3c29ca1d-17fb-4406-8293-b565b36c70d1
async def next_finding() -> None:
    """Show the oldest delegated finding (the FIFO head of the lane) with detail.

    The agent's "pull next work" surface. The rich context bundle (related
    files, guidance, rule text) is the deferred #653 exporter; for now this
    surfaces the finding's own payload so you know what to work next.
    """
    client = CoreApiClient()
    try:
        finding = await client.lane.next_delegated()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            console.print("[green]Lane is empty — no delegated findings.[/green]")
            return
        raise

    payload = finding.get("payload") or {}
    bundle = finding.get("bundle") or {}
    rule_info = bundle.get("rule") or {}
    remediation = bundle.get("remediation") or {}

    rule = rule_info.get("id") or payload.get("rule") or payload.get("rule_id") or "—"
    file = payload.get("file") or payload.get("file_path") or "—"
    message = payload.get("message") or payload.get("description") or ""
    claimed_by = payload.get("lane_claimed_by")
    created = (finding.get("created_at") or "")[:19].replace("T", " ")

    lines = [
        f"[bold]ID[/bold]       {finding['id']}",
        f"[bold]Subject[/bold]  {finding.get('subject', '')}",
        f"[bold]Rule[/bold]     [cyan]{rule}[/cyan]",
        f"[bold]File[/bold]     {file}",
        f"[bold]Created[/bold]  {created}",
    ]
    if claimed_by:
        lines.append(f"[bold]Claimed[/bold]  [yellow]{claimed_by}[/yellow]")
    if message:
        lines.append(f"\n{message}")

    # #653 context bundle — why the rule exists + the remediation hint.
    if rule_info.get("in_registry") is False:
        lines.append(
            "\n[yellow]⚠ This rule id is not in the active registry[/yellow] — "
            "likely renamed/retired (cf. #657). This finding should be "
            "[bold]resolved[/bold], not worked: no fix can clear a dead rule id."
        )
    if rule_info.get("rationale"):
        lines.append(f"\n[bold]Why this rule[/bold]\n{rule_info['rationale']}")
    if remediation.get("description"):
        status = remediation.get("status") or ""
        suffix = f" [dim]({status})[/dim]" if status else ""
        lines.append(
            f"\n[bold]Remediation guidance[/bold]{suffix}\n{remediation['description']}"
        )

    console.print(Panel("\n".join(lines), title="Assisted Lane — next finding"))
    console.print(
        "[dim]Claim it with `core-admin lane claim <id> --agent <you>`, then "
        "propose a fix with `core-admin lane propose <id> --patch <file>`.[/dim]"
    )
