# src/cli/resources/constitution/verify_bind.py
"""
`core-admin constitution verify` — pre-flight ADR bind verification.

Checks an ADR's supersession inheritance chain before the ADR is accepted by the
governor (#615). When an ADR declares "Supersedes: ADR-N", it claims to inherit
ADR-N's grounding. This command verifies the claim is sound: the declared
predecessor must carry either a grounding paper citation or its own Supersedes
declaration. A broken chain is reported with the specific failing link.

Grounding law: ADR-073 D6 (ROW2_GROUNDING) / topology §10.2 row 2.
Bind-verification extension: #615.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cli.utils import core_command
from mind.coherence.checks.row2_grounding import (
    _PAPERS_CITE,
    _STATUS_ACCEPTED,
    _SUPERSEDES_LINE,
    _extract_supersedes_adr_ids,
    _find_adr_file,
    adr_has_grounding_or_supersedes,
)

from . import app


console = Console()


@app.command("verify")
@core_command(dangerous=False, requires_context=False)
# ID: 8f3c2a1d-7b4e-4f6a-9c8d-e2b5f1a3c7d0
def verify_adr_bind(
    adr_path: Path = typer.Argument(
        ...,
        help=(
            "Path to the ADR .md file to check (e.g. "
            ".specs/decisions/ADR-141-my-decision.md)."
        ),
    ),
) -> None:
    """Pre-flight: verify an ADR's supersession inheritance chain has valid grounding.

    When an ADR claims to supersede a predecessor it inherits the predecessor's
    grounding. This command verifies the inherited bind is sound — the predecessor
    must carry either a grounding paper citation or its own Supersedes declaration.
    Run this before accepting an ADR that uses a Supersedes clause.

    Exit 0 on pass. Exit 1 on any broken link or missing predecessor.
    """
    path = Path(adr_path).resolve()
    if not path.is_file():
        console.print(f"[red]✗  File not found: {adr_path}[/red]")
        raise typer.Exit(1)

    repo_root = _find_repo_root(path)
    decisions = repo_root / ".specs" / "decisions"

    content = path.read_text(encoding="utf-8", errors="replace")
    adr_name = path.stem

    console.print(f"[bold]Verify-bind:[/bold] [cyan]{adr_name}[/cyan]\n")

    # Status check (advisory — command still runs on proposed ADRs for pre-flight)
    is_accepted = bool(_STATUS_ACCEPTED.search(content))
    status_label = "accepted" if is_accepted else "not yet accepted"
    console.print(f"  Status   : {status_label}")

    # Grounding via paper citation (no chain to verify)
    if _PAPERS_CITE.search(content):
        console.print("  Grounding: [green]direct paper citation present[/green]")
        console.print(f"\n[green]✓  {adr_name}: grounding verified (direct).[/green]")
        return

    supersedes_ids = _extract_supersedes_adr_ids(content)
    if not supersedes_ids:
        if _SUPERSEDES_LINE.search(content):
            console.print(
                "  Supersedes: declaration present but names no ADR "
                "(e.g. 'none' / 'nothing') — no bind to verify."
            )
            console.print(
                f"\n[yellow]⚠  {adr_name}: no paper citation and no inherited bind. "
                "ROW2_GROUNDING will fire if this ADR is accepted.[/yellow]"
            )
        else:
            console.print("  Supersedes: none declared")
            console.print(
                f"\n[yellow]⚠  {adr_name}: no paper citation and no Supersedes. "
                "ROW2_GROUNDING will fire if this ADR is accepted.[/yellow]"
            )
        raise typer.Exit(1)

    console.print(
        f"  Supersedes: {', '.join(supersedes_ids)} — verifying inherited bind(s)"
    )

    all_ok = True
    for sid in supersedes_ids:
        pred_file = _find_adr_file(sid, decisions)
        if pred_file is None:
            console.print(
                f"    [red]✗  {sid}: predecessor file not found in "
                f".specs/decisions/ — bind broken.[/red]"
            )
            all_ok = False
            continue
        pred_content = pred_file.read_text(encoding="utf-8", errors="replace")
        if adr_has_grounding_or_supersedes(pred_content):
            console.print(
                f"    [green]✓  {sid}: has grounding or its own supersedes "
                f"({pred_file.name})[/green]"
            )
        else:
            console.print(
                f"    [red]✗  {sid}: no grounding paper and no Supersedes "
                f"({pred_file.name}) — bind broken.[/red]"
            )
            all_ok = False

    if all_ok:
        console.print(
            f"\n[green]✓  {adr_name}: all inherited bind(s) verified.[/green]"
        )
    else:
        console.print(
            f"\n[red]✗  {adr_name}: one or more inherited binds are broken. "
            "Backfill the predecessor(s) with a grounding paper citation, "
            "or confirm the Supersedes declaration is correct.[/red]"
        )
        raise typer.Exit(1)


# ID: 1a4b3c2d-5e6f-4a7b-8c9d-0e1f2a3b4c5d
def _find_repo_root(start: Path) -> Path:
    """Walk up from start until we find .specs/decisions/."""
    candidate = start if start.is_dir() else start.parent
    for _ in range(12):
        if (candidate / ".specs" / "decisions").is_dir():
            return candidate
        candidate = candidate.parent
    raise RuntimeError(
        f"Could not locate repository root (no .specs/decisions/) from {start}"
    )
