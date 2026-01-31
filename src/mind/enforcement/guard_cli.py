# src/mind/enforcement/guard_cli.py

"""
CLI-facing guard registration helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from body.cli.logic.cli_utils import should_fail
from features.introspection.drift_detector import write_report
from features.introspection.drift_service import run_drift_analysis_async
from mind.enforcement.guard import _print_pretty, _ux_defaults
from shared.cli_utils import core_command


__all__ = ["guard_drift_cmd", "register_guard"]


# ID: 9c69d559-0c4a-4431-918b-14b3d588da91
@core_command(dangerous=False, requires_context=False)
# ID: b639850a-7321-4176-9891-dd24678bedb1
async def guard_drift_cmd(
    root: Path = typer.Option(Path("."), help="Repository root."),
    manifest_path: Path | None = typer.Option(
        None, help="Explicit manifest path (deprecated)."
    ),
    output: Path | None = typer.Option(None, help="Path for JSON evidence report."),
    format: str | None = typer.Option(None, help="json|table|pretty"),
    fail_on: str | None = typer.Option(None, help="any|missing|undeclared"),
) -> None:
    """
    Compares manifest vs code to detect capability drift.
    Exposed as a top-level callable so `status drift guard` can delegate here.
    """
    try:
        ux = _ux_defaults(root, manifest_path)
        fmt = (format or ux["default_format"]).lower()
        fail_policy = (fail_on or ux["default_fail_on"]).lower()

        report = await run_drift_analysis_async(root)
        report_dict: dict[str, Any] = report.to_dict()

        if ux["evidence_json"]:
            write_report(output or (root / ux["evidence_path"]), report)

        if fmt in ("table", "pretty"):
            _print_pretty(report_dict, ux["labels"])
        else:
            typer.echo(json.dumps(report_dict, indent=2))

        if should_fail(report_dict, fail_policy):
            raise typer.Exit(code=2)
    except FileNotFoundError as e:
        typer.secho(
            f"Error: A required constitutional file was not found: {e}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


# ID: a083eccb-0f7d-4230-b32c-4f9d9ae80ace
def register_guard(app: typer.Typer) -> None:
    """
    Registers the 'guard' command group with the CLI.
    """
    guard = typer.Typer(help="Governance/validation guards")
    app.add_typer(guard, name="guard")

    # Wire the group command to the canonical handler.
    guard.command("drift")(guard_drift_cmd)
