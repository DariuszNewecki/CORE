# src/cli/resources/law/apply.py

"""``core-admin law apply`` and ``law check-tree`` (ADR-170 Stage 1, D3).

``law apply <id>`` is the governor's approval of a law proposal. It runs
only as ``core-law`` under sudo; it reads the proposal once, checks it on a
scratch tree, shows refusals first, then CORE's computed warnings, then the
proposer's declared ones, then housekeeping, and writes only after the
governor types the proposal id.

``law check-tree`` runs the D5 data checks on the repository it is started
in. ``law apply`` runs it in a child process on the scratch tree; the
proposer can run it in a scratch worktree the same way.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console

from body.governance.law_custody.checks import CheckRunError, run_data_checks
from body.governance.law_custody.ledger import LedgerSignError
from body.governance.law_custody.proposal import ProposalError
from body.governance.law_custody.service import (
    PreparedApply,
    apply_prepared,
    prepare,
)
from body.governance.law_custody.writer import CustodyError, require_custodian
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.path_resolver import PathResolver
from shared.path_utils import get_repo_root

from .hub import app


console = Console()

# ADR-132 D10.13: the law beside CORE's code-only clone. A second destination
# when it exists; the report and the ledger line name every destination.
RELEASE_LAW_ROOT = Path("/opt/core/law")


@app.command("check-tree")
@command_meta(
    canonical_name="law.check-tree",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.MIND,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Run the law-apply data checks on the repository started in.",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 184921c4-8785-4776-87b0-5cf3b41b4442
async def law_check_tree(
    ctx: typer.Context,
    as_json: bool = typer.Option(False, "--json", help="Print one JSON line."),
) -> None:
    """
    Run the D5 refusal checks (schemas, references, the law loading,
    .claude/settings.json) on the repository in the working directory.
    Data only: no repository code runs. Exit 1 on any refusal.
    """
    report = await run_data_checks(get_repo_root(Path.cwd()))
    if as_json:
        typer.echo(json.dumps(report))
    else:
        for name, result in report["checks"].items():
            console.print(f"  {name}: {result}")
        for refusal in report["refusals"]:
            console.print(
                f"[red]REFUSED[/red] {refusal['check']}: {refusal['message']}"
            )
    if report["refusals"]:
        raise typer.Exit(1)


def _render(prepared: PreparedApply) -> None:
    proposal = prepared.proposal
    console.print(
        f"[bold]Law proposal {proposal.proposal_id}[/bold]  digest {proposal.digest[:16]}"
    )
    if prepared.refusals:
        console.print("[bold red]REFUSED -- nothing will be written:[/bold red]")
        for refusal in prepared.refusals:
            console.print(f"  [red]{refusal['check']}[/red]: {refusal['message']}")
        return
    console.print("\n[bold yellow]Warnings computed by CORE[/bold yellow]")
    if not prepared.computed_warnings:
        console.print("  none")
    for warning in prepared.computed_warnings:
        mark = "[bold red]WEAKENING[/bold red] " if warning.weakening else ""
        console.print(f"  {mark}{warning.category}: {warning.message} ({warning.path})")
    console.print(
        "\n[bold yellow]Warnings declared by the proposer[/bold yellow] "
        "(not checked by CORE)"
    )
    if not proposal.declared_warnings:
        console.print("  none declared")
    for item in proposal.declared_warnings:
        console.print(f"  - {item}")
    console.print("\n[bold]Checks[/bold] (data only; the full audit is not run here)")
    for name, result in prepared.checks.items():
        console.print(f"  {name}: {result}")
    groups = Counter(str(Path(p).parent) for p in proposal.paths())
    console.print("\n[bold]Housekeeping[/bold]")
    for directory, count in sorted(groups.items()):
        console.print(f"  {directory}/: {count} file(s)")
    if proposal.removals:
        console.print(f"  removed: {', '.join(proposal.removals)}")
    console.print(
        "\n[bold]Destinations[/bold]: "
        + ", ".join(str(d) for d in prepared.destinations)
    )


@app.command("apply")
@command_meta(
    canonical_name="law.apply",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.MIND,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Approve a law proposal: check, show, and on the typed id write it.",
    # Mutating: writes governed text. Without --write it shows the full report
    # and writes nothing; --write adds the typed-id approval (#824: the typed
    # id is an additional safeguard, never a substitute for --write).
    dangerous=True,
)
@core_command(dangerous=True, requires_context=False, requires_brain_services=False)
# ID: 16ac3eeb-4401-4e3f-ae83-1c744369f45b
async def law_apply(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(..., help="Proposal id, e.g. 0020-example."),
    repo: Path = typer.Option(
        None, "--repo", help="Development tree (default: discovered from cwd)."
    ),
    key: Path = typer.Option(
        None,
        "--key",
        help="core-law's ledger signing key (default ~/.ssh/core_law_ledger).",
    ),
    release_law: Path = typer.Option(
        RELEASE_LAW_ROOT,
        "--release-law",
        help="The law beside the release runtime; a second destination when it exists.",
    ),
    scratch: Path = typer.Option(
        None, "--scratch", help="Where the scratch tree is built (default ~/scratch)."
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Ask for the typed id and write. Without it, show the report only.",
    ),
) -> None:
    """
    Approve law proposal PROPOSAL_ID (ADR-170 D3). Run as:

      sudo -u core-law /opt/core-law/venv/bin/core-admin law apply <id> --write

    Refusals are shown first and nothing is written. Otherwise the warnings
    follow. Without --write nothing more happens; with --write the proposal
    is written to every destination, with one signed ledger line, only
    after you type the proposal id.
    """
    try:
        approver = require_custodian(os.environ)
    except CustodyError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(1)
    try:
        repo_root = (repo or get_repo_root(Path.cwd())).resolve()
    except FileNotFoundError:
        console.print(
            "[bold red]REFUSED -- nothing written:[/bold red] no repository with "
            ".intent/ above the working directory; run from the development "
            "tree (cd /opt/dev/CORE) or pass --repo."
        )
        raise typer.Exit(1)
    destinations = [repo_root]
    if release_law.is_dir():
        destinations.append(release_law)
    home = Path.home()
    try:
        prepared = prepare(
            repo_root=repo_root,
            proposals_dir=PathResolver(repo_root).var_dir / "law-proposals",
            proposal_id=proposal_id,
            destinations=destinations,
            scratch_parent=scratch or home / "scratch",
        )
    except (ProposalError, CustodyError, CheckRunError) as exc:
        console.print(f"[bold red]REFUSED -- nothing written:[/bold red] {exc}")
        raise typer.Exit(1)
    _render(prepared)
    if prepared.refusals:
        raise typer.Exit(1)
    if not write:
        console.print("\nReport only; nothing written. Re-run with --write to approve.")
        return
    if not sys.stdin.isatty():
        console.print(
            "[bold red]Approval needs a terminal; nothing written.[/bold red]"
        )
        raise typer.Exit(1)
    typed = typer.prompt(f"\nType the proposal id to approve ({proposal_id})")
    if typed.strip() != proposal_id:
        console.print("Not approved; nothing written.")
        raise typer.Exit(1)
    try:
        outcome = apply_prepared(
            prepared,
            approver=approver,
            key_path=key or home / ".ssh" / "core_law_ledger",
        )
    except (CustodyError, LedgerSignError) as exc:
        console.print(f"[bold red]REFUSED -- nothing written:[/bold red] {exc}")
        raise typer.Exit(1)
    for result in outcome.outcomes:
        state = f"[red]FAILED: {result.failed}[/red]" if result.failed else "written"
        console.print(
            f"  {result.root}: {state} ({len(result.written)} written, "
            f"{len(result.removed)} removed)"
        )
    if not outcome.ok():
        console.print(
            "[bold red]Not applied: no ledger line was written.[/bold red] "
            "The destinations above hold the bytes shown; run law apply again."
        )
        raise typer.Exit(1)
    console.print(
        f"[green]Applied {proposal_id}; ledger line appended "
        f"({len(outcome.outcomes)} destination(s)).[/green]"
    )
