# src/cli/commands/guard.py

"""CLI-facing guard registration helpers.

Thin client over /v1/status/drift (ADR-057 D3). The drift analysis runs
server-side; this CLI module renders the payload and writes evidence to
disk when requested.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from api.cli import CoreApiClient
from cli.logic.cli_utils import should_fail
from cli.utils import core_command
from shared.infrastructure.storage.file_handler import FileHandler


__all__ = ["guard_drift_cmd", "register_guard", "run_guard_drift"]


logger = logging.getLogger(__name__)


_DEFAULT_FORMAT = "json"
_DEFAULT_FAIL_ON = "any"
_DEFAULT_EVIDENCE_PATH = Path("reports") / "guard_drift.json"


# ID: 206eca11-fb40-4c24-af72-2c29376638c4
async def run_guard_drift(
    root: Path = Path("."),
    manifest_path: Path | None = None,
    output: Path | None = None,
    format: str | None = None,
    fail_on: str | None = None,
) -> None:
    """Compare manifest vs code to detect capability drift.

    Plain-args async helper. Callable from Python without Typer dependence;
    `guard_drift_cmd` is the Typer binding, and other CLI commands (e.g.
    `status drift guard`) call this helper directly to avoid OptionInfo
    leakage when invoking the work from non-Typer call sites.
    """
    _ = manifest_path  # The manifest path is resolved server-side.
    fmt = (format or _DEFAULT_FORMAT).lower()
    fail_policy = (fail_on or _DEFAULT_FAIL_ON).lower()

    client = CoreApiClient()
    try:
        report_dict = await client.status_drift(scope="all")
    except FileNotFoundError as exc:
        typer.secho(
            f"Error: A required constitutional file was not found: {exc}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from exc

    evidence_path = output or (root / _DEFAULT_EVIDENCE_PATH)
    file_handler = FileHandler(str(root))
    rel_evidence = str(evidence_path.relative_to(root))
    file_handler.ensure_dir(str(evidence_path.parent.relative_to(root)))
    file_handler.write_runtime_json(rel_evidence, report_dict)

    if fmt in {"table", "pretty"}:
        _print_pretty_report(report_dict)
    else:
        typer.echo(json.dumps(report_dict, indent=2))

    if should_fail(report_dict, fail_policy):
        raise typer.Exit(code=2)


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
    """Compare manifest vs code to detect capability drift.

    Typer binding. Delegates to `run_guard_drift` so the work is also
    callable from non-Typer call sites without OptionInfo leakage.
    """
    await run_guard_drift(
        root=root,
        manifest_path=manifest_path,
        output=output,
        format=format,
        fail_on=fail_on,
    )


def _print_pretty_report(report: dict) -> None:
    """Render a /v1/status/drift payload in plain text.

    Replaces `mind.enforcement.guard._print_pretty`, which was a CLI-side
    rendering helper that lived in the wrong layer. Drift scope keys
    ('symbols', 'vectors') map directly to sub-sections.
    """
    for section, payload in report.items():
        if not isinstance(payload, dict):
            typer.echo(f"{section}: {payload}")
            continue
        typer.echo(f"=== {section} ===")
        for key, value in payload.items():
            typer.echo(f"  {key}: {value}")


# ID: a083eccb-0f7d-4230-b32c-4f9d9ae80ace
def register_guard(app: typer.Typer) -> None:
    """Register the 'guard' command group with the CLI."""
    guard = typer.Typer(help="Governance/validation guards")
    app.add_typer(guard, name="guard")
    guard.command("drift")(guard_drift_cmd)
