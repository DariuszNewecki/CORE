# src/body/cli/commands/develop.py

"""
Unified interface for AI-native development with constitutional governance.

Commands for feature development, bug fixes, refactoring, and test generation
that automatically create intent crates for safe, autonomous deployment.

CONSTITUTIONAL FIX: Replaced Rich Progress() with logger.debug() progress logs.
Body layer must be HEADLESS - no UI components like Rich progress indicators.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from body.services.crate_creation_service import CrateCreationService
from body.services.crate_processing_service import process_crates
from features.autonomy.autonomous_developer import develop_from_goal
from shared.cli_utils import async_command
from shared.context import CoreContext
from shared.logger import getLogger
from will.agents.coder_agent import CoderAgent
from will.agents.execution_agent import _ExecutionAgent
from will.agents.plan_executor import PlanExecutor
from will.orchestration.prompt_pipeline import PromptPipeline


logger = getLogger(__name__)
console = Console()
develop_app = typer.Typer(
    help="AI-native development with constitutional governance", no_args_is_help=True
)


@develop_app.command()
@async_command
# ID: cc50b83e-c8da-4f00-968b-12d180ff7722
async def feature(
    ctx: typer.Context,
    description: str = typer.Argument(..., help="Feature description"),
    from_file: Path = typer.Option(None, help="Read description from file"),
    mode: str = typer.Option(
        "auto",
        help="Mode: 'auto' (create and process), 'manual' (create only), 'direct' (old behavior)",
    ),
):
    """
    Generate new feature with constitutional compliance.

    This command:
    1. Uses AI agents to generate code
    2. Validates against constitutional rules
    3. Creates an intent crate
    4. Submits for background processing

    Examples:
        # Generate feature and auto-process
        poetry run core-admin develop feature "Add rate limiting to API"

        # Generate but don't auto-process (for review)
        poetry run core-admin develop feature "Add JWT refresh" --mode manual

        # Read description from file
        poetry run core-admin develop feature --from-file requirements.txt
    """
    context: CoreContext = ctx.obj
    if context is None:
        console.print("[red]Error: Context not initialized[/red]")
        raise typer.Exit(code=1)
    if from_file:
        if not from_file.exists():
            console.print(f"[red]Error: File not found: {from_file}[/red]")
            raise typer.Exit(code=1)
        goal = from_file.read_text(encoding="utf-8").strip()
    else:
        goal = description.strip()
    if not goal:
        console.print("[red]Error: Empty description provided[/red]")
        raise typer.Exit(code=1)
    console.print(
        Panel.fit(
            f"[bold cyan]Autonomous Feature Development[/bold cyan]\n\nGoal: {goal}\nMode: {mode}",
            border_style="cyan",
        )
    )
    cognitive_service = context.cognitive_service
    if not cognitive_service and context.registry:
        logger.info("Initializing CognitiveService...")
        try:
            cognitive_service = await context.registry.get_cognitive_service()
            context.cognitive_service = cognitive_service
        except Exception as e:
            console.print(
                f"[red]Error: Could not initialize CognitiveService: {e}[/red]"
            )
            console.print(
                "[yellow]Check that LLM API URLs are configured in runtime_settings[/yellow]"
            )
            raise typer.Exit(code=1)
    if not cognitive_service:
        console.print(
            "[red]Error: CognitiveService is required for autonomous development[/red]"
        )
        raise typer.Exit(code=1)
    qdrant_service = context.qdrant_service
    if not qdrant_service and context.registry:
        logger.info("Initializing Qdrant for semantic development...")
        try:
            qdrant_service = await context.registry.get_qdrant_service()
            if cognitive_service:
                cognitive_service._qdrant_service = qdrant_service
        except Exception as e:
            logger.warning(
                "Could not initialize Qdrant: %s. Proceeding without semantic context.",
                e,
            )
    prompt_pipeline = PromptPipeline(context.git_service.repo_path)
    plan_executor = PlanExecutor(
        context.file_handler, context.git_service, context.planner_config
    )
    coder_agent = CoderAgent(
        cognitive_service=cognitive_service,
        prompt_pipeline=prompt_pipeline,
        auditor_context=context.auditor_context,
        qdrant_service=qdrant_service,
    )
    executor_agent = _ExecutionAgent(
        coder_agent=coder_agent,
        plan_executor=plan_executor,
        auditor_context=context.auditor_context,
    )

    # CONSTITUTIONAL FIX: Use logger.debug() instead of Rich Progress()
    # Body layer must be headless - no UI components
    logger.debug("Starting code generation with AI agents...")
    console.print("\n[dim]Generating code with AI agents...[/dim]")

    output_mode = "crate" if mode in ("auto", "manual") else "direct"
    success, result = await develop_from_goal(
        context, goal, executor_agent, output_mode=output_mode
    )

    logger.debug("Code generation completed: success=%s", success)

    if not success:
        console.print("\n[bold red]✗ Code generation failed[/bold red]")
        console.print(f"Error: {result}")
        raise typer.Exit(code=1)
    if mode == "direct":
        console.print(
            "\n[bold green]✓ Code generated and applied directly[/bold green]"
        )
        console.print(result)
        return
    console.print("\n[bold]Creating intent crate...[/bold]")
    try:
        crate_service = CrateCreationService()
        files_generated = result.get("files", {})
        generation_metadata = {
            "context_tokens": result.get("context_tokens", 0),
            "generation_tokens": result.get("generation_tokens", 0),
            "validation_passed": result.get("validation_passed", True),
        }
        crate_id = crate_service.create_intent_crate(
            intent=goal,
            payload_files=files_generated,
            crate_type="STANDARD",
            metadata=generation_metadata,
        )
        console.print(f"[bold green]✓ Created crate: {crate_id}[/bold green]")
        console.print(f"\nLocation: work/crates/inbox/{crate_id}")
        console.print(f"Files: {len(files_generated)}")
        console.print("\n[bold]Payload:[/bold]")
        for file_path in files_generated.keys():
            console.print(f"  • {file_path}")
        if mode == "auto":
            console.print("\n[dim]Crate submitted for automatic processing.[/dim]")
            console.print(
                "[dim]Background daemon will validate via canary and deploy if safe.[/dim]"
            )
            console.print(
                f"\nTrack status: [cyan]core-admin crate status {crate_id}[/cyan]"
            )
            await process_crates()
        else:
            console.print(
                "\n[yellow]Manual mode: Crate created but not submitted for processing.[/yellow]"
            )
            console.print(
                f"Review and process: [cyan]core-admin crate process {crate_id}[/cyan]"
            )
    except Exception as e:
        console.print("\n[bold red]✗ Failed to create crate[/bold red]")
        console.print(f"Error: {e}")
        logger.error("Crate creation failed: %s", e, exc_info=True)
        raise typer.Exit(code=1)


@develop_app.command()
@async_command
# ID: 3bf4b18d-b099-4eb3-9572-a1c81f761630
async def fix(
    ctx: typer.Context,
    description: str = typer.Argument(..., help="Bug description"),
    from_file: Path = typer.Option(None, help="Read description from file"),
    mode: str = typer.Option("auto", help="Mode: auto, manual, or direct"),
):
    """
    Generate bug fix with constitutional compliance.

    Examples:
        poetry run core-admin develop fix "JWT validation fails on expired tokens"
        poetry run core-admin develop fix --from-file bug-report.txt
    """
    await feature(ctx, description, from_file, mode)


@develop_app.command()
@async_command
# ID: fb64c80d-ae84-4792-a032-54c22071909d
async def test(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="Module path to generate tests for"),
    mode: str = typer.Option("auto", help="Mode: auto, manual, or direct"),
):
    """
    Generate tests for a module with constitutional compliance.

    Examples:
        poetry run core-admin develop test src/services/git_service.py
        poetry run core-admin develop test services.llm_client --mode manual
    """
    goal = f"Generate comprehensive tests for {target}"
    await feature(ctx, goal, None, mode)


@develop_app.command()
@async_command
# ID: d18c7126-5bb2-4feb-8810-031f5ffdba2d
async def refactor(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="What to refactor"),
    description: str = typer.Option("", help="Refactoring description (optional)"),
    mode: str = typer.Option("auto", help="Mode: auto, manual, or direct"),
):
    """
    Perform refactoring with constitutional compliance.

    Examples:
        poetry run core-admin develop refactor "Extract retry logic from llm_client"
        poetry run core-admin develop refactor services.llm_client --description "Reduce complexity"
    """
    if description:
        goal = f"Refactor {target}: {description}"
    else:
        goal = f"Refactor {target}"
    await feature(ctx, goal, None, mode)


@develop_app.command()
# ID: d2c8a1d6-f58a-4278-be58-487c317ba878
def info():
    """
    Show information about the autonomous development system.
    """
    console.print(
        Panel.fit(
            "[bold cyan]CORE Autonomous Development System (A2 Ready)[/bold cyan]\n\n[bold]Available Commands:[/bold]\n  • feature   - Generate new features\n  • fix       - Generate bug fixes\n  • test      - Generate tests\n  • refactor  - Perform refactoring\n\n[bold]Modes:[/bold]\n  • auto   - Create crate and process automatically (default)\n  • manual - Create crate but wait for manual processing\n  • direct - Apply changes immediately (legacy)\n\n[bold]Architecture:[/bold]\n  • Semantic Infrastructure: [green]Active[/green]\n  • Constitutional RAG: [green]Active[/green]\n  • Canary Validation: [green]Active[/green]",
            border_style="cyan",
        )
    )
