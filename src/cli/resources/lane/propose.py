# src/cli/resources/lane/propose.py
"""`core-admin lane propose` — submit a validated agent diff for a delegated finding."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)

console = Console()

_VALIDATE_ACTION = "assisted.validate_diff"


@core_command(dangerous=False, requires_context=False)
# ID: e0f6bd92-4391-4d80-b0e7-40f2e5f32de6
async def propose(
    finding_id: str = typer.Argument(
        ..., help="Delegated finding id (from `lane list`)."
    ),
    patch_file: Path = typer.Option(
        ...,
        "--patch",
        "-p",
        help="Path to the unified diff the agent produced for this finding.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Validate an agent-authored diff and, if it clears, submit it for approval.

    Flow (ADR-109): read the finding's rule, run ``assisted.validate_diff``
    against the diff in a throwaway worktree (apply + ruff + the offending rule
    must no longer fire + mapped tests), and only on a clean verdict create the
    human-gated proposal and move the finding out of the inbox into "being
    worked". A diff that fails validation never reaches the approval queue.
    """
    client = CoreApiClient()

    # 1. Recover the finding's rule — the gate needs it, and a 404 here means
    #    the finding is not a live lane item (already worked / not delegated).
    finding = await client.lane.get_delegated(finding_id)
    payload = finding.get("payload") or {}
    rule = payload.get("rule") or payload.get("rule_id") or "unknown"

    # The finding's subject file — the gate validates that the rule no longer
    # flags *this* file, not just the diff's touched files (ADR-109 mechanism
    # §4; needed when the fix lives in a different file than the subject, e.g.
    # a detector-bug fix). Prefer the payload; fall back to the subject's
    # trailing "lang::rule::path" segment.
    subject_file = payload.get("file") or payload.get("file_path")
    if not subject_file:
        subject = finding.get("subject") or ""
        if "::" in subject:
            subject_file = subject.rsplit("::", 1)[-1] or None
    subject_files = [subject_file] if subject_file else []

    patch = patch_file.read_text(encoding="utf-8")

    # 2. Validate the diff in a hermetic worktree via the general action-run
    #    surface (decoupled from this command's process).
    console.print(f"[dim]Validating diff against rule [cyan]{rule}[/cyan]…[/dim]")
    run = await client.run_fix(
        _VALIDATE_ACTION,
        params={
            "patch": patch,
            "finding_rule": rule,
            "subject_files": subject_files,
        },
    )
    run_id = run["run_id"]
    terminal = await client._poll_run(run_id)
    result = terminal.get("result") or {}
    data = result.get("data") or {}

    if not result.get("ok"):
        console.print("[red]Validation failed — diff is not approvable.[/red]")
        for check, passed in (data.get("validation_results") or {}).items():
            mark = "[green]✓[/green]" if passed else "[red]✗[/red]"
            console.print(f"  {mark} {check}")
        if data.get("error"):
            console.print(f"  [red]{data['error']}[/red]")
        raise typer.Exit(code=1)

    # 3. Ingest the validated diff as a governed, human-gated proposal. The
    #    endpoint re-reads the persisted verdict (run_id) before creating it.
    proposed = await client.lane.propose(
        finding_id, patch=patch, validation_run_id=run_id
    )
    files = proposed.get("scope_files", [])
    console.print(
        f"[green]Validated and proposed.[/green] Proposal "
        f"[cyan]{proposed['proposal_id']}[/cyan] "
        f"({len(files)} file(s)) is awaiting your approval."
    )
    console.print(
        "[dim]Review and approve with "
        "`core-admin proposals approve <proposal-id>`.[/dim]"
    )
