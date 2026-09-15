# src/cli/resources/workers/export_run.py
"""
`core-admin workers export-run <run_id>` -- export one goal-driven run's
Blackboard record as a deterministic JSON file (#893).

Operator surface only (ADR-146 D3: `workers/` stays in CORE). Reads the
ledger through `BlackboardQueryService.fetch_entries_by_run_id`, builds the
document with `body.services.blackboard_service.blackboard_run_export`, and
writes the bytes via FileHandler to the canonical path
`var/exports/blackboard_runs/<run_id>.json` (PathResolver.exports_dir; not
configurable, same stance as `database export`). `--stdout` emits the
identical bytes on the raw stdout buffer instead -- not through Rich, which
wraps.

Refusals are exit 1 with the reason on the console and nothing written:
`no_entries` (unknown run_id or a run that recorded nothing -- the Blackboard
cannot tell these apart) and `run_incomplete` (no `goal_run.<id>.outcome`
entry: in flight or died without one). `--partial` opts into exporting the
latter with `"completeness": "partial"` stamped in the file.

The export time is printed to the console and is deliberately absent from
the file, so re-exporting the same run yields the same bytes.

ADR-159 D4 adaptation accounting: new module under `src/` -- thesis-negative
adaptation, recorded per the `goal_execution_worker.py` worked pattern. It
adds retrieval only; what is recorded (item 3) and what is targeted (item 1)
are untouched.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from body.infrastructure.storage.file_handler import FileHandler
from body.services.blackboard_service.blackboard_query_service import (
    BlackboardQueryService,
)
from body.services.blackboard_service.blackboard_run_export import (
    RunExportRefused,
    build_run_export,
    serialize_run_export,
)
from cli.utils.decorators import core_command
from shared.path_resolver import PathResolver

from .run import workers_app


console = Console()

_EXPORT_SUBDIR = "blackboard_runs"


@workers_app.command("export-run")
@core_command(dangerous=False)
# ID: 38892d48-1bfe-4bee-af5d-93722427b3ab
async def export_run_cmd(
    ctx: typer.Context,
    run_id: str = typer.Argument(
        ..., help="The run_id GoalExecutionWorker stamped (goal_run.<run_id>.*)."
    ),
    partial: bool = typer.Option(
        False,
        "--partial",
        help="Export a run with no outcome entry, stamped completeness=partial.",
    ),
    to_stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Write the export bytes to stdout instead of the canonical file.",
    ),
) -> None:
    """Export everything the Blackboard recorded for one run (read-only)."""
    entries = await BlackboardQueryService().fetch_entries_by_run_id(run_id)
    try:
        document = build_run_export(run_id, entries, allow_partial=partial)
    except RunExportRefused as exc:
        console.print(f"[red]Export refused ({exc.reason}):[/red] {exc.detail}")
        if exc.reason == "run_incomplete":
            console.print(
                "Pass [cyan]--partial[/cyan] to export it stamped as partial."
            )
        raise typer.Exit(1) from exc

    payload = serialize_run_export(document)

    if to_stdout:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        return

    repo_root = Path(ctx.obj.git_service.repo_path).resolve()
    export_dir = PathResolver(repo_root).exports_dir / _EXPORT_SUBDIR
    rel_dir = export_dir.relative_to(repo_root).as_posix()
    rel_path = f"{rel_dir}/{run_id}.json"
    handler = FileHandler(str(repo_root))
    handler.ensure_dir(rel_dir)
    handler.write_runtime_bytes(rel_path, payload)

    recon = document["reconciliation"]
    exported_at = datetime.now(UTC).isoformat()
    console.print(f"[green]Exported[/green] {rel_path}")
    console.print(
        f"  run_id={run_id} completeness={document['completeness']} "
        f"entries={recon['entry_count']} by_type={recon['counts_by_entry_type']}"
    )
    console.print(
        f"  first={recon['first_created_at']} last={recon['last_created_at']}"
    )
    binding = document.get("target_binding")
    if binding is None:
        console.print("  target_binding=none (CORE-internal run)")
    else:
        console.print(
            f"  target_binding: subject={binding['subject_sha'][:12]} "
            f"copy={binding['bound_sha'][:12]} floor={binding['floor_hash'][:12]} "
            f"overlay={binding['overlay_hash'][:12]} displaced={len(binding['displaced'])}"
        )
    console.print(f"  exported_at={exported_at} (console only; not in the file)")
    if document["completeness"] == "partial":
        console.print(
            "[yellow]PARTIAL:[/yellow] no outcome entry -- this file is not the whole run."
        )
