# src/cli/resources/law/access.py

"""``core-admin law access`` — the access register against reality (rule 5).

Read-only. Compares the register in ``.intent/taxonomies/principal_roles.yaml``
with the host's accounts, groups, governor binding, sudo rules and governed
file modes, and with GitHub's collaborators and ruleset bypass list. What
this account cannot read is listed as not evaluated, never as passed: run it
as root for the sudo rules, with ``CORE_GITHUB_TOKEN`` for GitHub.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from body.services.access_register import (
    check_github_access,
    check_host,
    load_register,
)
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


@app.command("access")
@command_meta(
    canonical_name="law.access",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Check the access register against the host and GitHub (rule 5).",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 1d18ce97-1467-4bfe-acb7-08d4048323d3
async def law_access(
    ctx: typer.Context,
    as_json: bool = typer.Option(False, "--json", help="Print one JSON line."),
) -> None:
    """
    Every account, group, sudo rule and GitHub collaborator not in the
    register is a blocking finding (ADR-068 amendment 2026-10-15, rule 5).
    Exit 1 on any finding.
    """
    repo = get_repo_root(Path.cwd())
    register = load_register(PathResolver(repo).intent_root)
    report = check_host(register, repo_root=repo)
    await check_github_access(register, report)
    if as_json:
        typer.echo(json.dumps(report.as_dict()))
    else:
        for finding in report.findings:
            console.print(f"[red]BLOCKING[/red] {finding.message}")
        for check, reason in report.not_evaluated.items():
            console.print(f"[yellow]NOT EVALUATED[/yellow] {check}: {reason}")
        console.print(
            f"evaluated: {', '.join(report.evaluated)}; "
            f"{len(report.findings)} blocking finding(s)"
        )
    if report.findings:
        raise typer.Exit(1)
