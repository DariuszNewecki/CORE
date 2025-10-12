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


# ID: 79e03609-2875-4dfa-ab67-e8435f994a0c
async def check_integration_health(context: CoreContext) -> bool:
    """
    Runs the full integration and validation sequence without committing or rolling back.
    This is the primary developer command to check if work is ready to be committed.
    Returns True if all checks pass, False otherwise.
    """
    cognitive_service = context.cognitive_service

    try:
        console.print("\n[bold]Step 1/5: Assigning IDs to new symbols...[/bold]")
        assign_missing_ids(dry_run=False)

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

        # The service layer now only returns the result, it does not print it.
        if not passed:
            # Store findings in a temporary context for the CLI to pick up.
            # This is a pragmatic way to pass data between service and CLI layer.
            context.auditor_context.last_findings = findings
            return False

        console.print(
            "\n[bold green]✅ All integration checks passed. Your changes are ready to be committed.[/bold green]"
        )
        return True

    except Exception as e:
        console.print(f"\n[bold red]An error occurred during the check: {e}[/bold red]")
        return False


# ID: a6ace728-0c7f-48b8-b7a0-52ff9b24d99d
async def integrate_changes(context: CoreContext, commit_message: str):
    """
    Orchestrates the full, transactional, and intelligent integration of staged code changes.
    """
    git_service = context.git_service
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

        if await check_integration_health(context):
            console.print("\n[bold]Final Step: Committing changes...[/bold]")
            git_service.add_all()
            git_service.commit(commit_message)
            console.print(
                "[bold green]✅ Successfully integrated and committed changes.[/bold green]"
            )
            integration_succeeded = True
        else:
            raise RuntimeError(
                "Integration health check failed. Triggering automatic rollback."
            )

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
