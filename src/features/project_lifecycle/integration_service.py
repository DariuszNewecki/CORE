# src/features/project_lifecycle/integration_service.py
from __future__ import annotations

from rich.console import Console
from shared.config import settings
from shared.context import CoreContext

from features.governance.constitutional_auditor import ConstitutionalAuditor
from features.introspection.sync_service import run_sync_with_db
from features.introspection.vectorization_service import run_vectorize
from features.project_lifecycle.definition_service import define_new_symbols
from features.self_healing.id_tagging_service import assign_missing_ids

console = Console()


# ID: 47b10dad-7f52-4962-bc07-7b82a2c12f42
async def integrate_changes(context: CoreContext, commit_message: str):
    """
    Orchestrates the full, transactional, and intelligent integration of staged code changes.
    """
    # Get services from the explicitly passed context object
    git_service = context.git_service
    cognitive_service = context.cognitive_service

    initial_commit_hash = git_service.get_current_commit()
    integration_succeeded = False

    try:
        staged_files = git_service.get_staged_files()
        if not staged_files:
            console.print(
                "[yellow]No staged changes found to integrate. Please use 'git add'.[/yellow]"
            )
            return

        console.print(f"Integrating {len(staged_files)} staged file(s)...")

        # --- START OF TRANSACTIONAL & REORDERED PROCESS ---

        console.print("\n[bold]Step 1/5: Assigning IDs to new symbols...[/bold]")
        assign_missing_ids(
            dry_run=False
        )  # This is the only step that modifies local files
        git_service.add_all()

        console.print(
            "\n[bold]Step 2/5: Synchronizing code state with the database...[/bold]"
        )
        await run_sync_with_db()

        await cognitive_service.initialize()

        console.print(
            "\n[bold]Step 3/5: Vectorizing new and modified symbols...[/bold]"
        )
        await run_vectorize(
            cognitive_service=cognitive_service, dry_run=False, force=False
        )

        console.print(
            "\n[bold]Step 4/5: Autonomously defining new capabilities...[/bold]"
        )
        await define_new_symbols(cognitive_service)

        console.print("\n[bold]Step 5/5: Running full constitutional audit...[/bold]")
        auditor = ConstitutionalAuditor(settings.REPO_PATH)
        passed, findings, _ = await auditor.run_full_audit_async()
        if not passed:
            console.print(
                "[bold red]❌ Constitutional audit failed. Integration will be reverted.[/bold red]"
            )
            # This ensures the 'finally' block triggers a reset
            raise RuntimeError("Audit failed, triggering automatic rollback.")

        console.print("\n[bold]Final Step: Committing changes...[/bold]")
        git_service.commit(commit_message)
        console.print(
            "[bold green]✅ Successfully integrated and committed changes.[/bold green]"
        )
        integration_succeeded = True

        # --- END OF TRANSACTIONAL & REORDERED PROCESS ---

    except Exception as e:
        console.print(
            f"\n[bold red]An error occurred during integration: {e}[/bold red]"
        )
        console.print("[bold red]Aborting and reverting all changes...[/bold red]")

    finally:
        if not integration_succeeded:
            console.print(
                f"   -> Reverting repository to clean state at commit {initial_commit_hash[:7]}..."
            )
            git_service.reset_to_commit(initial_commit_hash)
            console.print(
                "[bold yellow]✅ Rollback complete. Your working directory is clean.[/bold yellow]"
            )
