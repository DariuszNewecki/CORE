# src/features/project_lifecycle/bootstrap_service.py

"""
Provides CLI commands for bootstrapping the project with initial setup tasks,
such as creating a default set of GitHub issues for a new repository.
"""

from __future__ import annotations

import shutil
import subprocess

import typer

from shared.logger import getLogger


logger = getLogger(__name__)
bootstrap_app = typer.Typer(
    help="Commands for project bootstrapping and initial setup."
)

ISSUES_TO_CREATE = [
    {
        "title": "Add JSON logging & request IDs",
        "body": (
            "**Goal**: Switch logger to support LOG_FORMAT=json and add request-id "
            "middleware in FastAPI.\n\n"
            "**Acceptance**\n"
            "- LOG_FORMAT=json writes structured logs\n"
            "- x-request-id is set and propagated\n"
            "- Documentation updated in docs/CONVENTIONS.md"
        ),
        "labels": "roadmap,organizational,ci",
    },
    {
        "title": "Pre-commit hooks (Black, Ruff)",
        "body": (
            "**Goal**: Add .pre-commit-config.yaml and wire it into Make.\n\n"
            "**Acceptance**\n"
            "- pre-commit runs Black and Ruff locally\n"
            "- CI remains green"
        ),
        "labels": "roadmap,organizational,ci",
    },
    {
        "title": "Docs: CONVENTIONS.md & DEPENDENCIES.md",
        "body": (
            "**Goal**: Codify folder structure, import rules, capability tags, "
            "and dependency policy.\n\n"
            "**Acceptance**\n"
            "- New contributors can place files without guidance\n"
            "- Import discipline matrix documented"
        ),
        "labels": "roadmap,organizational,docs",
    },
    {
        "title": "Governance: proposal schema & lifecycle validation",
        "body": (
            "**Goal**: Define and validate the proposal lifecycle for "
            "`work/proposals/`.\n\n"
            "**Acceptance**\n"
            "- Proposals are treated as operational artefacts (not constitutional files)\n"
            "- Auditor ignores `work/` for schema enforcement\n"
            "- Proposal approval flow is exercised end-to-end\n"
            "- At least one example proposal exists under work/proposals/"
        ),
        "labels": "roadmap,organizational,audit",
    },
]

LABELS_TO_ENSURE = [
    {"name": "roadmap", "color": "0366d6", "desc": "Roadmap item"},
    {"name": "organizational", "color": "a2eeef", "desc": "Project organization"},
    {"name": "ci", "color": "7057ff", "desc": "CI/CD"},
    {"name": "audit", "color": "d73a4a", "desc": "Governance & audit"},
    {"name": "docs", "color": "0e8a16", "desc": "Documentation"},
]


def _run_gh_command(command: list[str], ignore_errors: bool = False):
    """Helper to run a 'gh' command and handle errors."""
    if not shutil.which("gh"):
        logger.error("'gh' (GitHub CLI) not found in PATH.")
        logger.info("Install GitHub CLI to use bootstrap features.")
        raise typer.Exit(code=1)

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            logger.error("Error running gh command: %s", e.stderr)
            raise typer.Exit(code=1)


@bootstrap_app.command("issues")
# ID: 4a6eaa79-3261-4e31-9f43-e2e5a96c4276
def bootstrap_issues(
    repo: str | None = typer.Option(
        None, "--repo", help="GitHub repository in 'owner/repo' format."
    ),
):
    """Create a standard set of starter issues for the project on GitHub."""
    logger.info("Bootstrapping standard GitHub issues...")
    logger.info("Ensuring required labels exist...")

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

    logger.info("Creating %s starter issues...", len(ISSUES_TO_CREATE))

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

    logger.info("Successfully created starter issues on GitHub.")
