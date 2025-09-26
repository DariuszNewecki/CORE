# src/features/project_lifecycle/integration_service.py
from __future__ import annotations

from rich.console import Console

from core.git_service import GitService
from features.governance.constitutional_auditor import ConstitutionalAuditor
from features.introspection.sync_service import run_sync_with_db
from features.introspection.vectorization_service import run_vectorize
from features.project_lifecycle.definition_service import define_new_symbols
from features.self_healing.id_tagging_service import assign_missing_ids
from shared.config import settings

console = Console()


# ID: 47b10dad-7f52-4962-bc07-7b82a2c12f42
async def integrate_changes(commit_message: str):
    """
    Orchestrates the full, autonomous integration of staged code changes.
    """
    git_service = GitService(settings.REPO_PATH)

    # 1. Check for staged changes
    staged_files = git_service.get_staged_files()
    if not staged_files:
        console.print(
            "[yellow]No staged changes found to integrate. Please use 'git add'.[/yellow]"
        )
        return

    console.print(f"Integrating {len(staged_files)} staged file(s)...")

    # 2. Assign IDs to new symbols
    console.print("\n[bold]Step 1/5: Assigning IDs to new symbols...[/bold]")
    assign_missing_ids(dry_run=False)
    # Re-stage any files that were modified by the ID tagger
    git_service.add_all()

    # 3. Synchronize with the database
    console.print(
        "\n[bold]Step 2/5: Synchronizing code state with the database...[/bold]"
    )
    await run_sync_with_db()

    # 4. Autonomously define new symbols
    console.print("\n[bold]Step 3/5: Autonomously defining new capabilities...[/bold]")
    await define_new_symbols()

    # 5. Vectorize new symbols
    console.print("\n[bold]Step 4/5: Vectorizing new symbols...[/bold]")
    await run_vectorize(
        dry_run=False, force=False
    )  # force=False ensures we only vectorize new things

    # 6. Constitutional Audit
    console.print("\n[bold]Step 5/5: Running full constitutional audit...[/bold]")
    auditor = ConstitutionalAuditor(settings.REPO_PATH)
    passed, findings, _ = await auditor.run_full_audit_async()
    if not passed:
        console.print(
            "[bold red]❌ Constitutional audit failed. Integration aborted.[/bold red]"
        )
        # Optionally, print findings here
        return

    # 7. Git Commit
    console.print("\n[bold]Final Step: Committing changes...[/bold]")
    git_service.commit(commit_message)
    console.print(
        "[bold green]✅ Successfully integrated and committed changes.[/bold green]"
    )
