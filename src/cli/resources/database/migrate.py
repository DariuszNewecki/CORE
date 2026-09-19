# src/cli/resources/database/migrate.py
"""
Database migration command (ADR-162 D1, D3, D7).

Applies pending SQL migrations recorded in infra/migrations/manifest.yaml
against core._migrations. The canonical schema for a fresh install is the
repository-root ``schema.sql`` (which seeds the ledger, D9); this ledger
handles incremental changes on existing databases.

Modes — only ``--write`` mutates anything (``cli.command.dangerous_marking``):

    core-admin database migrate                          # dry run: list pending
    core-admin database migrate --write                  # apply pending, atomically
    core-admin database migrate --adopt-baseline v2.9.1  # verify only (dry run)
    core-admin database migrate --adopt-baseline v2.9.1 --write   # record baseline

``--apply`` survives one release as a deprecated alias for ``--write``.
``--bootstrap`` is retired: it recorded every manifest entry as applied without
verifying anything, which marked a stale schema as current (ADR-162 D3).

Execution (ADR-162 D7): each pending migration runs in ONE transaction
together with its ``core._migrations`` row, under a fixed advisory lock with
the ledger re-read inside the lock. A failure leaves that migration fully
rolled back and unrecorded; earlier ones stay recorded; re-running is safe.
Files may keep a leading ``BEGIN;`` / trailing ``COMMIT;`` (stripped by the
engine); any other transaction control or non-transactional statement is
refused before anything executes. An entry declared ``reconcilable`` whose
verify probe already holds is recorded without execution (D12 §2).

Refused (fail closed): an empty ledger on a populated schema (adopt a verified
baseline first) and a ledger/schema contradiction (a recorded entry whose
probe fails). Upgrading an existing database remains UNSUPPORTED until the
release that ships ADR-162 U2-U7; these commands are unreleased.

Workflow going forward:
    # 1. Write infra/scripts/migrations/YYYYMMDD_description.sql
    # 2. Append filename to infra/migrations/manifest.yaml order list
    #    (with a `verify` probe under `probes:`)
    # 3. core-admin database migrate --write
"""

from __future__ import annotations

import typer
from rich.console import Console

from cli.utils import core_command
from shared.infrastructure.repositories.db.migration_service import (
    MigrationServiceError,
    adopt_baseline,
    migrate_db,
)

from .hub import app


console = Console()


@app.command("migrate")
@core_command(dangerous=True, requires_context=False)
# ID: d8b7978f-d801-4ba2-a669-f0fd48851b01
async def migrate_database(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Execute pending migrations (or record the adopted baseline). "
        "Without this flag nothing is mutated.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="DEPRECATED alias for --write; removed next release.",
    ),
    adopt_baseline_tag: str | None = typer.Option(
        None,
        "--adopt-baseline",
        metavar="TAG",
        help=(
            "Verify that the database is at the declared baseline TAG (e.g. v2.9.1) "
            "and, with --write, record the manifest entries through it. Refuses "
            "unless every probe of TAG holds and no later baseline also holds."
        ),
    ),
) -> None:
    """Show pending migrations, apply them, or adopt a verified baseline.

    Dry run (default): prints pending migration IDs from the manifest.
    --write: executes pending SQL files, each atomically with its ledger row.
    --adopt-baseline TAG [--write]: verifies TAG's probes; records ≤ TAG.
    """
    if apply:
        console.print(
            "[yellow]--apply is deprecated;[/yellow] use --write. "
            "Treating as --write for this release."
        )
        write = True
    try:
        if adopt_baseline_tag is not None:
            adoption = await adopt_baseline(adopt_baseline_tag, write=write)
            if write:
                console.print(
                    f"[green]Baseline {adoption.tag} adopted.[/green] "
                    f"{len(adoption.recorded)} ledger row(s) recorded through "
                    f"{adoption.through}."
                )
            else:
                console.print(
                    f"[green]Baseline {adoption.tag} verified.[/green] "
                    f"{len(adoption.to_record)} ledger row(s) would be recorded "
                    f"through {adoption.through}. Pass --write to record them."
                )
            return

        report = await migrate_db(write=write)
        if not write:
            console.print(
                f"[yellow]Dry run.[/yellow] {len(report.pending_before)} pending. "
                "Pass --write to execute pending migrations."
            )
            for mig in report.pending_before:
                console.print(f"  • {mig}")
        else:
            console.print(
                f"[green]Migrations complete.[/green] "
                f"{len(report.applied)} applied, {len(report.reconciled)} reconciled, "
                f"{len(report.skipped)} skipped."
            )
    except MigrationServiceError as exc:
        console.print(f"[red]Migration error:[/red] {exc}")
        raise typer.Exit(code=exc.exit_code) from exc
