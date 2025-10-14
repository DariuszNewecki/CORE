# src/features/project_lifecycle/integration_service.py
from __future__ import annotations

import subprocess

import typer
from rich.console import Console
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

log = getLogger("integration_service")
console = Console()


# ID: a6ace728-0c7f-48b8-b7a0-52ff9b24d99d
async def integrate_changes(context: CoreContext, commit_message: str):
    """
    Orchestrates the full, non-destructive, and intelligent integration of code changes
    by executing the constitutionally-defined `integration_workflow`.

    This workflow is designed to be safe and developer-friendly. If it fails,
    it halts and leaves the working directory in its current state for the
    developer to fix. It will never destroy uncommitted work.
    """
    git_service = context.git_service
    workflow_failed = False

    try:
        # Step 1: Stage all current work. This captures the developer's full intent.
        console.print("[bold]Step 1: Staging all current changes...[/bold]")
        git_service.add_all()
        staged_files = git_service.get_staged_files()
        if not staged_files:
            console.print(
                "[yellow]No changes found to integrate. Working directory is clean.[/yellow]"
            )
            return

        console.print(f"   -> Staged {len(staged_files)} file(s) for integration.")

        # Step 2: Load and execute the constitutional workflow.
        workflow_policy = settings.load("charter.policies.operations.workflows_policy")
        integration_steps = workflow_policy.get("integration_workflow", [])

        for i, step in enumerate(integration_steps, 1):
            console.print(
                f"\n[bold]Step {i + 1}/{len(integration_steps) + 2}: {step['description']}[/bold]"
            )
            command_parts = step["command"].split()

            # --- THIS IS THE FIX ---
            # Run the command without `check=True` so we can handle the failure gracefully.
            process = subprocess.run(
                command_parts,
                capture_output=True,
                text=True,
                cwd=settings.REPO_PATH,
            )

            # Print output regardless of success
            if process.stdout:
                console.print(process.stdout)
            if process.stderr:
                console.print(f"[yellow]{process.stderr}[/yellow]")

            # Now, manually check the return code.
            if process.returncode != 0:
                console.print(f"[bold red]❌ Step '{step['id']}' failed.[/bold red]")

                if not step.get("continues_on_failure", False):
                    console.print(
                        "\n[bold red]Integration halted. Please fix the error above, then re-run the command.[/bold red]"
                    )
                    workflow_failed = True
                    break  # Exit the loop immediately
                else:
                    console.print(
                        "   -> [yellow]Continuing because step is marked as non-blocking.[/yellow]"
                    )
            # --- END OF FIX ---

        if workflow_failed:
            raise Exception("Workflow halted due to a failed step.")

        # Step 3: All checks passed. Stage any new changes and commit.
        console.print(
            f"\n[bold]Step {len(integration_steps) + 2}/{len(integration_steps) + 2}: Committing all changes...[/bold]"
        )
        git_service.commit(commit_message)
        console.print(
            "[bold green]✅ Successfully integrated and committed changes.[/bold green]"
        )

    except Exception as e:
        log.error(f"Integration process failed: {e}")
        # The user-friendly message is now printed inside the loop.
        # We can exit gracefully here.
        raise typer.Exit(code=1)
