# src/cli/resources/law/verify.py

"""``core-admin law verify`` — check every custody ledger signature (#1112).

Read-only. Each line of the ledger of record (the host's durable ledger when
it has one, otherwise ``.intent/custody/ledger.jsonl``) is checked with
``ssh-keygen -Y verify`` against ``.intent/custody/allowed_signers``, for the
identity and namespace ``law apply`` signs with. Every line that does not
verify is listed; exit 1 when any fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from body.governance.law_custody.ledger import (
    ALLOWED_SIGNERS_REL,
    ledger_file,
    verify_ledger,
)
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.path_utils import get_repo_root

from .hub import app


console = Console()


@app.command("verify")
@command_meta(
    canonical_name="law.verify",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Verify every custody ledger line's signature against allowed_signers.",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: ea095bea-9463-4189-81fc-08c5de2bf1dc
async def law_verify(
    ctx: typer.Context,
    ledger: Path = typer.Option(
        None, "--ledger", help="Ledger to check (default: the ledger of record)."
    ),
    allowed_signers: Path = typer.Option(
        None,
        "--allowed-signers",
        help=f"Allowed signers file (default: <repo>/{ALLOWED_SIGNERS_REL}).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print one JSON line."),
) -> None:
    """
    Check each ledger line with ssh-keygen -Y verify and list every line
    that does not verify. Exit 1 when any line fails or the ledger is missing.
    """
    repo = get_repo_root(Path.cwd())
    ledger_path = ledger or ledger_file(repo)
    signers = allowed_signers or repo / ALLOWED_SIGNERS_REL
    for path in (ledger_path, signers):
        if not path.is_file():
            console.print(f"[red]not found:[/red] {path}")
            raise typer.Exit(1)
    checked, failures = verify_ledger(ledger_path, signers)
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "ledger": str(ledger_path),
                    "allowed_signers": str(signers),
                    "checked": checked,
                    "failed": [{"line": n, "reason": r} for n, r in failures],
                }
            )
        )
    else:
        for number, reason in failures:
            console.print(f"[red]FAIL[/red] line {number}: {reason}")
        console.print(
            f"{ledger_path}: {checked} line(s) checked, {len(failures)} failed "
            f"(allowed signers: {signers})"
        )
    if failures:
        raise typer.Exit(1)
