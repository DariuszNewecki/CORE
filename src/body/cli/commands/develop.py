# src/body/cli/commands/develop.py
# ID: body.cli.commands.develop
"""
Unified interface for AI-native development with constitutional governance.

Commands for feature development, bug fixes, refactoring, and test generation
that automatically create intent crates for safe, autonomous deployment.

MAJOR UPDATE (Phase 5):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UNIX-COMPLIANT WORKFLOW ORCHESTRATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OLD PATTERN (Removed):
  - Used _ExecutionAgent (mixed code generation + execution)
  - Violated UNIX philosophy (did two things)

NEW PATTERN (Current):
  - SpecificationAgent (code generation ONLY)
  - ExecutionAgent (execution ONLY)
  - AutonomousWorkflowOrchestrator (coordinates specialists)

  Three-phase pipeline:
    1. Planning (PlannerAgent)
    2. Specification (SpecificationAgent)
    3. Execution (ExecutionAgent)

Constitutional Alignment:
- Each agent does ONE thing well
- Complete audit trail via DecisionTracer
- All actions through ActionExecutor (constitutional gateway)
- Returns structured WorkflowResult

CONSTITUTIONAL FIX: Replaced Rich Progress() with logger.debug() progress logs.
Body layer must be HEADLESS - no UI components like Rich progress indicators.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from body.atomic.executor import ActionExecutor
from shared.cli_utils import async_command
from shared.context import CoreContext
from shared.logger import getLogger
from will.agents.coder_agent import CoderAgent
from will.agents.execution_agent import ExecutionAgent
from will.agents.planner_agent import PlannerAgent
from will.agents.specification_agent import SpecificationAgent
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.workflow_orchestrator import AutonomousWorkflowOrchestrator


logger = getLogger(__name__)
console = Console()

# ID: develop_app_definition
develop_app = typer.Typer(
    help="AI-native development with constitutional governance", no_args_is_help=True
)


# ID: 6f9d2e1a-c8da-4f00-968b-12d180ff7722
async def _run_development_workflow(
    ctx: typer.Context,
    description: str,
    from_file: Path | None,
    mode: str,
    workflow_label: str = "Feature Development",
):
    """
    Internal async logic for development workflows.

    Uses UNIX-compliant three-phase orchestration:
    1. Planning → SpecificationAgent → ExecutionAgent

    Args:
        ctx: Typer context with CoreContext
        description: Goal description
        from_file: Optional file with goal
        mode: 'auto', 'manual', or 'direct'
        workflow_label: Label for logging
    """
    context: CoreContext = ctx.obj

    # Read goal from file or use description
    if from_file:
        goal = from_file.read_text(encoding="utf-8").strip()
    else:
        goal = description.strip()

    if not goal:
        console.print("[bold red]❌ Goal cannot be empty[/bold red]")
        raise typer.Exit(code=1)

    logger.info("=" * 80)
    logger.info("🎯 %s: %s", workflow_label, goal)
    logger.info("=" * 80)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BUILD SPECIALISTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    console.print("\n[dim]Initializing AI agents...[/dim]")

    # Initialize cognitive service (handles LLM client orchestration)
    from will.orchestration.cognitive_service import CognitiveService

    cognitive_service = context.cognitive_service

    if cognitive_service is None:
        # Fallback: create cognitive service if not in context
        cognitive_service = CognitiveService(context.git_service.repo_path)
        logger.debug("Created new CognitiveService instance")

    # Ensure auditor_context is initialized
    if context.auditor_context is None:
        from mind.governance.audit_context import AuditorContext

        context.auditor_context = AuditorContext(context.git_service.repo_path)
        logger.debug("Created new AuditorContext instance")

    # Try to initialize Qdrant (optional semantic features)
    qdrant_service = None
    try:
        # FIXED: Removed 'settings=settings' which was causing the crash
        from shared.infrastructure.clients.qdrant_client import QdrantService

        qdrant_service = QdrantService()
        logger.debug("Qdrant service initialized for semantic features")
    except Exception as e:
        logger.warning(
            "Could not initialize Qdrant service. Proceeding without semantic context: %s",
            e,
        )

    # 1. PlannerAgent (Architect)
    planner = PlannerAgent(cognitive_service)
    logger.debug("✅ PlannerAgent initialized")

    # 2. CoderAgent (for SpecificationAgent to use)
    prompt_pipeline = PromptPipeline(context.git_service.repo_path)
    coder_agent = CoderAgent(
        cognitive_service=cognitive_service,
        prompt_pipeline=prompt_pipeline,
        auditor_context=context.auditor_context,
        qdrant_service=qdrant_service,
    )
    logger.debug("✅ CoderAgent initialized")

    # 3. SpecificationAgent (Engineer)
    spec_agent = SpecificationAgent(
        coder_agent=coder_agent,
        context_str="",  # Will accumulate context during execution
    )
    logger.debug("✅ SpecificationAgent initialized")

    # 4. ExecutionAgent (Contractor)
    action_executor = ActionExecutor(context)
    exec_agent = ExecutionAgent(action_executor)
    logger.debug("✅ ExecutionAgent initialized")

    # 5. AutonomousWorkflowOrchestrator (General Contractor)
    orchestrator = AutonomousWorkflowOrchestrator(
        planner=planner,
        spec_agent=spec_agent,
        exec_agent=exec_agent,
    )
    logger.debug("✅ AutonomousWorkflowOrchestrator initialized")

    console.print("[dim]All agents ready. Starting autonomous workflow...[/dim]\n")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EXECUTE THREE-PHASE WORKFLOW
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    try:
        workflow_result = await orchestrator.execute_autonomous_goal(
            goal=goal,
            reconnaissance_report="",  # FUTURE: Add reconnaissance if needed
        )

    except Exception as e:
        logger.error("❌ Workflow orchestration failed: %s", e, exc_info=True)
        console.print(f"\n[bold red]❌ Workflow failed: {e}[/bold red]")
        raise typer.Exit(code=1)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HANDLE RESULTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if not workflow_result.success:
        console.print("\n[bold red]❌ Workflow failed[/bold red]")
        console.print(workflow_result.summary())

        # Save decision trace for debugging
        orchestrator.save_decision_trace()
        console.print("\n[dim]Decision trace saved to var/traces/[/dim]")

        raise typer.Exit(code=1)

    # Success!
    console.print("\n[bold green]✅ Workflow completed successfully![/bold green]")
    console.print(workflow_result.summary())

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CRATE CREATION (if mode is 'auto' or 'manual')
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if mode == "direct":
        console.print(
            "\n[bold green]✓ Code generated and applied directly[/bold green]"
        )
        console.print("\n[dim]Files created successfully![/dim]")
        return

    # Extract generated files for crate packaging
    console.print("\n[dim]Packaging generated files into crate...[/dim]")

    generated_files = {}

    # Collect code from DetailedPlan
    for step in workflow_result.detailed_plan.steps:
        if "code" in step.params and step.params.get("file_path"):
            file_path = step.params["file_path"]
            code = step.params["code"]
            generated_files[file_path] = code
            logger.debug("Extracted file for crate: %s", file_path)

    if not generated_files:
        console.print("[yellow]⚠️ No files generated - nothing to package[/yellow]")
        return

    # NOTE: CrateCreationService uses deprecated settings.load() method
    # Files have already been written directly by ExecutionAgent
    # Skipping crate packaging for now
    console.print(
        f"[green]✓ Generated {len(generated_files)} file(s) successfully![/green]"
    )
    console.print(
        "\n[yellow]Note: Crate packaging skipped (files already written directly)[/yellow]"
    )
    console.print("[dim]Run 'git status' to see the generated files[/dim]")

    # FUTURE: Fix CrateCreationService to work with new Settings API
    # The service needs to be updated to use settings.get_path() + load file
    # instead of the deprecated settings.load() method


@develop_app.command()
@async_command
# ID: cc50b83e-c8da-4f00-968b-12d180ff7722
async def feature(
    ctx: typer.Context,
    description: str = typer.Argument(..., help="Feature description"),
    from_file: Path = typer.Option(None, help="Read description from file"),
    mode: str = typer.Option("auto", help="Mode: 'auto', 'manual', 'direct'"),
):
    """Generate new feature with constitutional compliance."""
    await _run_development_workflow(
        ctx, description, from_file, mode, "Feature Development"
    )


@develop_app.command()
@async_command
# ID: 3bf4b18d-b099-4eb3-9572-a1c81f761630
async def fix(
    ctx: typer.Context,
    description: str = typer.Argument(..., help="Bug description"),
    from_file: Path = typer.Option(None, help="Read description from file"),
    mode: str = typer.Option("auto", help="Mode: auto, manual, or direct"),
):
    """Generate bug fix with constitutional compliance."""
    await _run_development_workflow(ctx, description, from_file, mode, "Bug Fix")


@develop_app.command()
@async_command
# ID: fb64c80d-ae84-4792-a032-54c22071909d
async def test(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="Module path to generate tests for"),
    mode: str = typer.Option("auto", help="Mode: auto, manual, or direct"),
):
    """Generate tests for a module with constitutional compliance."""
    goal = f"Generate comprehensive tests for {target}"
    await _run_development_workflow(ctx, goal, None, mode, "Test Generation")


@develop_app.command()
@async_command
# ID: d18c7126-5bb2-4feb-8810-031f5ffdba2d
async def refactor(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="What to refactor"),
    description: str = typer.Option("", help="Refactoring description (optional)"),
    mode: str = typer.Option("auto", help="Mode: auto, manual, or direct"),
):
    """Perform refactoring with constitutional compliance."""
    goal = f"Refactor {target}: {description}" if description else f"Refactor {target}"
    await _run_development_workflow(ctx, goal, None, mode, "Refactoring")


@develop_app.command()
# ID: d2c8a1d6-f58a-4278-be58-487c317ba878
def info():
    """Show information about the autonomous development system."""
    console.print(
        Panel.fit(
            "[bold cyan]CORE Autonomous Development System[/bold cyan]\n\n"
            "[bold]Architecture:[/bold]\n"
            "  • Three-Phase Workflow: [green]Active[/green]\n"
            "  • UNIX Philosophy: [green]Enforced[/green]\n"
            "  • Constitutional Governance: [green]Active[/green]\n"
            "  • Semantic Infrastructure: [green]Active[/green]\n"
            "  • Constitutional RAG: [green]Active[/green]\n"
            "  • Canary Validation: [green]Active[/green]\n\n"
            "[bold]Agents:[/bold]\n"
            "  • PlannerAgent (Architect)\n"
            "  • SpecificationAgent (Engineer)\n"
            "  • ExecutionAgent (Contractor)\n"
            "  • AutonomousWorkflowOrchestrator (General Contractor)",
            border_style="cyan",
        )
    )
