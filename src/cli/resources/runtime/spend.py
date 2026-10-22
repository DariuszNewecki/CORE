# src/cli/resources/runtime/spend.py
"""
``core-admin runtime spend`` — what CORE's LLM calls cost (ADR-172).

Reads CORE's API (``GET /v1/status/spend``), the same answer the MCP tool
core_status carries. Read-only; without a running API it says so.
"""

from __future__ import annotations

from typing import Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from cli.utils import async_command

from .health import runtime_app
from .status import API


console = Console()


# ID: 9d3a6f12-4e8b-4c71-a2f5-6b0e8d1c3f47
def render_spend(spend: dict[str, Any]) -> None:
    """Print the per-day and per-role tables and the total line."""
    days = Table(title="Per UTC day", box=None, header_style="bold")
    for name in ("Day", "Calls", "USD", "Unpriced"):
        days.add_column(name, justify="left" if name == "Day" else "right")
    for d in spend.get("by_day") or []:
        days.add_row(d["day"], str(d["calls"]), f"{d['usd']:.4f}", str(d["unpriced"]))
    console.print(days)

    roles = Table(title="Per role and model", box=None, header_style="bold")
    roles.add_column("Role")
    roles.add_column("Model")
    for name in ("Calls", "Tokens in", "Tokens out", "USD", "USD/call", "Unpriced"):
        roles.add_column(name, justify="right")
    for r in spend.get("by_role_model") or []:
        roles.add_row(
            r["role"],
            r["model"],
            str(r["calls"]),
            f"{r['prompt_tokens']:,}",
            f"{r['completion_tokens']:,}",
            f"{r['usd']:.4f}",
            f"{r['usd_per_call']:.5f}",
            str(r["unpriced"]),
        )
    console.print(roles)
    line = (
        f"[bold]Last {spend.get('days')} days:[/bold] USD {spend.get('usd', 0):.4f} "
        f"in {spend.get('calls', 0)} calls"
    )
    if spend.get("unpriced"):
        line += f"; {spend['unpriced']} calls without a price (not in the total)"
    console.print(line)


@runtime_app.command("spend")
@async_command
# ID: 1b8e4c7d-6a29-4f03-9e5b-c2d7a0f84e16
async def spend_cmd(
    days: int = typer.Option(7, "--days", "-d", help="How many days back"),
    api: str = typer.Option(API, "--api"),
) -> None:
    """What CORE's LLM calls cost: per day, per role and model."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api}/v1/status/spend", params={"days": days}, timeout=30
            )
            response.raise_for_status()
            spend = response.json()
    except Exception as exc:
        console.print(f"[red]CORE's API could not be reached: {exc}[/red]")
        raise typer.Exit(1)
    render_spend(spend)
