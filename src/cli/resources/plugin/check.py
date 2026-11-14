# src/cli/resources/plugin/check.py
"""`core-admin plugin check <name>` (ADR-177 D7): one installed plug-in
against the contract. The report is meant to be kept as validation evidence."""

from __future__ import annotations

import json
import sys

import typer

from body.services.plugin_check import PluginCheckReport, check_installed_plugin
from cli.utils import core_command

from . import app


EXIT_CONFORMS, EXIT_PROBLEMS, EXIT_ERROR = 0, 1, 3


def _render_text(report: PluginCheckReport) -> str:
    verdict = "conforms" if report.conforms else "does not conform"
    lines = [
        f"Plug-in {report.name} {report.version}: {verdict}",
        f"Loaded: {'yes' if report.loaded else 'no'}",
    ]
    if report.loaded:
        lines += [
            f"Fingerprint: {report.fingerprint}",
            f"core_engine_api: {report.core_engine_api}",
            f"Engines: {', '.join(report.engines) or 'none'}",
            f"Catalogs: {', '.join(report.catalogs) or 'none'}",
            f"Packs: {', '.join(report.packs) or 'none'}",
        ]
    lines.append("")
    lines.append("Problems:" if report.problems else "Problems: none")
    for p in report.problems:
        lines.append(f"  {p.rule}  {p.subject}: {p.message}")
    return "\n".join(lines)


@app.command("check")
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 22972b31-5da4-4eb8-a6bd-60d7e543669d
async def check_command(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="The plug-in's package name, as installed."),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="`text` (default) or `json` (format plugin-check/1).",
    ),
) -> None:
    """Check an installed plug-in against the plug-in contract (ADR-177).

    Checks the manifest, each engine (declarations, a run on a minimal
    input), id collisions with CORE and other plug-ins, and the plug-in's
    catalogs and packs. Exit codes: 0 conforms, 1 problems found, 3 the
    command could not run (no such plug-in, bad option). Stores nothing.

    Examples:
        core-admin plugin check my-plugin
        core-admin plugin check my-plugin --format json > plugin-check.json
    """
    code, text = await run_check(name, output_format)
    if code == EXIT_ERROR:
        typer.echo(text, err=True)
    elif output_format == "json":
        sys.stdout.write(text + "\n")
    else:
        typer.echo(text)
    raise typer.Exit(code)


# ID: b408a650-4b95-45fe-8dca-c2c0a9788926
async def run_check(name: str, output_format: str) -> tuple[int, str]:
    """The command without the terminal: (exit code, text to print)."""
    if output_format not in ("text", "json"):
        return EXIT_ERROR, f"--format must be text or json (got {output_format!r})"
    try:
        report = await check_installed_plugin(name)
    except Exception as exc:  # could not run, never a verdict
        return EXIT_ERROR, f"plugin check could not run: {type(exc).__name__}: {exc}"
    if report is None:
        return (
            EXIT_ERROR,
            f"plugin check could not run: no installed plug-in named {name!r}",
        )
    text = (
        json.dumps(report.to_dict(), indent=2)
        if output_format == "json"
        else _render_text(report)
    )
    return (EXIT_CONFORMS if report.conforms else EXIT_PROBLEMS), text
