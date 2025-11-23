# scripts/nightly_coverage_remediation.py
"""
The orchestrator for the nightly autonomous coverage remediation job.

This script implements the "foreman" for the testing agent:
1. Ensures the local repository is clean and synchronized with the remote.
2. Checks if it is within its allowed operational time window (can be bypassed).
3. Analyzes the codebase to find files with low test coverage.
4. For each low-coverage file, it identifies "SIMPLE" functions as candidates.
5. It creates a prioritized queue of files to fix.
6. It invokes the `core-admin coverage remediate --file` command for each
   file in the queue, continuing until the time window ends or no simple
   targets remain.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# --- START OF FIX: Add all necessary imports for CoreContext ---
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from body.services.file_handler import FileHandler
from body.services.git_service import GitService
from features.self_healing.coverage_watcher import watch_and_remediate
from mind.governance.audit_context import AuditorContext
from services.clients.qdrant_client import QdrantService
from services.knowledge_service import KnowledgeService
from shared.config import settings
from shared.context import CoreContext
from shared.models import PlannerConfig
from will.orchestration.cognitive_service import CognitiveService

# --- END OF FIX ---


console = Console()

# --- Configuration ---
START_HOUR = 22  # 10 PM
END_HOUR = 7  # 7 AM


def _ensure_clean_and_synced_workspace() -> bool:
    """
    Performs a pre-flight check to ensure the repo is clean and up-to-date.
    """
    console.print("[bold cyan]Step 0: Verifying workspace state...[/bold cyan]")
    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=settings.REPO_PATH,
        )
        if status_result.stdout.strip():
            console.print(
                "[bold red]❌ Error: Your workspace has uncommitted changes.[/bold red]"
            )
            console.print(
                "   Please commit or stash your changes before running the agent."
            )
            return False

        console.print("   -> Fetching latest changes from remote...")
        subprocess.run(
            ["git", "pull", "--rebase"],
            check=True,
            capture_output=True,
            text=True,
            cwd=settings.REPO_PATH,
        )
        console.print("[green]   -> ✅ Workspace is clean and up-to-date.[/green]")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        console.print(f"[bold red]❌ Git command failed: {e}[/bold red]")
        if isinstance(e, subprocess.CalledProcessError):
            console.print(f"[red]{e.stderr}[/red]")
        return False


def _is_within_operating_window() -> bool:
    """Checks if the current time is within the allowed window."""
    current_hour = datetime.now().hour
    if START_HOUR > END_HOUR:
        return current_hour >= START_HOUR or current_hour < END_HOUR
    else:
        return START_HOUR <= current_hour < END_HOUR


async def _async_main():
    """The main async entry point for the remediation script."""
    force_run = "--now" in sys.argv

    console.print(
        Panel(
            f"[bold green]🚀 Starting Autonomous Coverage Remediation[/bold green]\n"
            f"Operational Window: {START_HOUR}:00 - {END_HOUR}:00",
            expand=False,
        )
    )

    if not _ensure_clean_and_synced_workspace():
        console.print(
            Panel(
                "[bold red]❌ Pre-flight checks failed. Aborting run.[/bold red]",
                expand=False,
            )
        )
        return

    if not force_run and not _is_within_operating_window():
        console.print(
            f"\n[bold yellow]🕓 Current time is outside the operational window ({START_HOUR}:00 - {END_HOUR}:00). Halting run.[/bold yellow]"
        )
        return

    # === START OF FIX ===
    # Construct the full CoreContext toolbox here, at the top-level entry point.
    context = CoreContext(
        git_service=GitService(settings.REPO_PATH),
        cognitive_service=CognitiveService(settings.REPO_PATH),
        knowledge_service=KnowledgeService(settings.REPO_PATH),
        qdrant_service=QdrantService(),
        auditor_context=AuditorContext(settings.REPO_PATH),
        file_handler=FileHandler(str(settings.REPO_PATH)),
        planner_config=PlannerConfig(),
    )

    # Pass the context to the watcher service.
    result = await watch_and_remediate(context=context, auto_remediate=True)
    # === END OF FIX ===

    console.print(
        Panel(
            f"[bold green]✅ Remediation Run Finished. Final Status: {result.get('status', 'unknown')}[/bold green]",
            expand=False,
        )
    )


def main():
    """Synchronous entry point for the script."""
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
