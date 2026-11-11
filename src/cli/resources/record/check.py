# src/cli/resources/record/check.py
"""`core-admin record check <record.json> --catalog <id>` (ADR-173, #1328).

Judges one resolved record against a record catalog and prints the verdict.
Read-only: it reads two files and stores nothing; no API, no database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer
from typer.core import TyperCommand

from body.services.grc.record_catalog import (
    RecordInputError,
    check_record,
    read_record,
)
from cli.utils import core_command
from mind.logic.record_contract import RecordVerdict, verdict_to_dict

from . import app


# Exit codes, also stated in the command's help.
EXIT_PASS, EXIT_FAIL, EXIT_UNDECIDED, EXIT_ERROR = 0, 1, 2, 3
_EXIT = {"pass": EXIT_PASS, "fail": EXIT_FAIL, "undecided": EXIT_UNDECIDED}


class _UsageErrorExitsThree(TyperCommand):
    """A usage error (missing argument, unknown option) exits 3, "could not
    run", instead of click's 2, which this command uses for undecided."""

    # ID: 6e1f8a2b-4d3c-4b7e-9a5f-0c2d8e7b1a64
    def parse_args(self, ctx: Any, args: list[str]) -> Any:
        try:
            return super().parse_args(ctx, args)
        except Exception as exc:
            # Typer bundles its own click; match its usage errors by their
            # exit code rather than by a private class.
            if getattr(exc, "exit_code", None) == 2:
                setattr(exc, "exit_code", EXIT_ERROR)
            raise


def _render_text(verdict: RecordVerdict, catalog: str, rule_count: int) -> str:
    lines = [
        f"Verdict: {verdict.outcome} ({verdict.evidence_class.value})",
        f"Record sha256: {verdict.record_sha256}",
        f"Catalog: {catalog} ({rule_count} rules)",
        "",
        "Rules:",
    ]
    width = max((len(p.rule_id) for p in verdict.parts), default=0)
    for part in verdict.parts:
        lines.append(
            f"  {part.rule_id:<{width}}  {part.result:<9}  {part.evidence_class.value}"
        )
    with_findings = [p for p in verdict.parts if p.findings]
    lines += ["", "Findings:" if with_findings else "Findings: none"]
    for part in with_findings:
        lines.append(f"  {part.rule_id}")
        for f in part.findings:
            message = f.message
            if f.item and message.startswith(f"{f.item}: "):
                message = message[len(f.item) + 2 :]
            kind = "blocking" if f.blocking else "not blocking"
            where = f.item or "(record)"
            lines.append(f"    {where} ({kind}): {message}")
    return "\n".join(lines)


@app.command("check", cls=_UsageErrorExitsThree)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: c0de2b4a-974c-4da8-bb66-aef1ad150ef3
async def check_command(
    ctx: typer.Context,
    record_file: Path = typer.Argument(
        ..., help="The record to judge: a library-snapshot/1 JSON file."
    ),
    catalog: str = typer.Option(
        ..., "--catalog", "-c", help="Record catalog id, e.g. publication_rules."
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="`text` (default): the verdict in plain words. `json`: the full "
        "verdict, format record-verdict/1.",
    ),
) -> None:
    """Judge a resolved record against a record catalog and print the verdict.

    Exit codes: 0 pass, 1 fail, 2 undecided (a human must decide), 3 the
    command could not run (unreadable record, unknown catalog, bad option).
    Stores nothing.

    Examples:
        # Plain words
        core-admin record check snapshot.json --catalog publication_rules

        # Full verdict as JSON
        core-admin record check snapshot.json --catalog publication_rules --format json
    """
    if output_format not in ("text", "json"):
        typer.echo(f"--format must be text or json (got {output_format!r})", err=True)
        raise typer.Exit(EXIT_ERROR)
    try:
        record = read_record(record_file)
        verdict, rule_count = await check_record(record, catalog)
    except RecordInputError as exc:
        typer.echo(f"record check could not run: {exc}", err=True)
        raise typer.Exit(EXIT_ERROR) from exc
    except Exception as exc:  # any other failure is "could not run", never a fail
        typer.echo(f"record check could not run: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(EXIT_ERROR) from exc
    if output_format == "json":
        sys.stdout.write(json.dumps(verdict_to_dict(verdict), indent=2) + "\n")
    else:
        typer.echo(_render_text(verdict, catalog, rule_count))
    raise typer.Exit(_EXIT[verdict.outcome])
