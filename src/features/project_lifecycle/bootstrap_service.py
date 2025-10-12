# src/features/project_lifecycle/bootstrap_service.py
"""
Provides CLI commands for bootstrapping the project with initial setup tasks,
such as creating a default set of GitHub issues for a new repository.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

import typer
from rich.console import Console
from shared.logger import getLogger

log = getLogger("core_admin.bootstrap")
console = Console()

bootstrap_app = typer.Typer(
    help="Commands for project bootstrapping and initial setup."
)

ISSUES_TO_CREATE = [
    {
        "title": "Add JSON logging & request IDs",
        "body": "**Goal**: Switch logger to support LOG_FORMAT=json and add request id middleware in FastAPI.\n\n**Acceptance**\n- LOG_FORMAT=json writes structured logs\n- x-request-id is set/propagated\n- Docs updated in docs/CONVENTIONS.md",
        "labels": "roadmap,organizational,ci",
    },
    {
        "title": "Pre-commit hooks (Black, Ruff)",
        "body": "**Goal**: Add .pre-commit-config.yaml and wire to Make.\n\n**Acceptance**\n- pre-commit runs Black/Ruff locally\n- CI stays green",
        "labels": "roadmap,organizational,ci",
    },
    {
        "title": "Docs: CONVENTIONS.md & DEPENDENCIES.md",
        "body": "**Goal**: Codify folder map, import rules, capability tags, dependency policy.\n\n**Acceptance**\n- New contributors can place files w/o asking\n- Import discipline matrix documented",
        "labels": "roadmap,organizational,docs",
    },
    {
        "title": "Governance: proposal.schema.json + proposal_checks",
        "body": "**Goal**: Enforce schema & drift checks for .intent/proposals.\n\n**Acceptance**\n- Auditor shows schema pass/fail\n- Drift (token mismatch) → warning\n- Example proposal present",
        "labels": "roadmap,organizational,audit",
    },
]

LABELS_TO_ENSURE = [
    {"name": "roadmap", "color": "0366d6", "desc": "Roadmap item"},
    {"name": "organizational", "color": "a2eeef", "desc": "Project organization"},
    {"name": "ci", "color": "7057ff", "desc": "CI/CD"},
    {"name": "audit", "color": "d73a4a", "desc": "Constitutional audit & governance"},
    {"name": "docs", "color": "0e8a16", "desc": "Documentation"},
]


def _run_gh_command(command: list[str], ignore_errors: bool = False):
    """Helper to run a 'gh' command and handle errors."""
    if not shutil.which("gh"):
        console.print(
            "[bold red]❌ 'gh' (GitHub CLI) command not found in your PATH.[/bold red]"
        )
        console.print("   -> Please install it to use this feature.")
        raise typer.Exit(code=1)
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            console.print(f"[bold red]Error running gh command: {e.stderr}[/bold red]")
            raise typer.Exit(code=1)


@bootstrap_app.command("issues")
# ID: 695834ae-f6a1-49ed-baa8-7e99276df2ac
def bootstrap_issues(
    repo: Optional[str] = typer.Option(
        None, "--repo", help="The GitHub repository in 'owner/repo' format."
    ),
):
    """Creates a standard set of starter issues for the project on GitHub."""
    console.print("[bold cyan]🚀 Bootstrapping standard GitHub issues...[/bold cyan]")

    console.print("   -> Ensuring required labels exist...")
    for label in LABELS_TO_ENSURE:
        cmd = [
            "gh",
            "label",
            "create",
            label["name"],
            "--color",
            label["color"],
            "--description",
            label["desc"],
        ]
        if repo:
            cmd.extend(["--repo", repo])
        _run_gh_command(cmd, ignore_errors=True)

    console.print(f"   -> Creating {len(ISSUES_TO_CREATE)} starter issues...")
    for issue in ISSUES_TO_CREATE:
        cmd = [
            "gh",
            "issue",
            "create",
            "--title",
            issue["title"],
            "--body",
            issue["body"],
            "--label",
            issue["labels"],
        ]
        if repo:
            cmd.extend(["--repo", repo])
        _run_gh_command(cmd)

    console.print(
        "[bold green]✅ Successfully created starter issues on GitHub.[/bold green]"
    )


# The obsolete `register` function has been removed.
