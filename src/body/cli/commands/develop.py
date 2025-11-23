# ID: 57c10949-8476-4de6-b883-fa7c14b0e580
# ID: eab8bd1f-a196-48bc-bec1-41249f00a302
# ID: 031702d1-abda-4a03-bbe6-10e25098561f
# ID: 17f6c506-f0da-44fa-997b-214fa2027a6d
# ID: cd01f725-a0ff-431c-9f41-5c622dbd4e3f
# ID: c4bc5c5c-4642-47dd-9bbd-65f6985a2ce7
# ID: a74d5275-484f-4abd-9e41-ad77f28091c2
# ID: 92e07dcc-75e0-4d7a-8d39-352dc031f00f
# ID: 3845021d-cb17-4aaa-8783-6c538a95400f
# ID: 517a4a90-82d6-4e15-8faf-36ec019335d0
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.commands.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: development.cli.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# ID: cli.develop.execute
# src/body/cli/commands/develop.py

"""
Unified interface for AI-native development with constitutional governance.

Commands for feature development, bug fixes, refactoring, and test generation
that automatically create intent crates for safe, autonomous deployment.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from body.services.crate_creation_service import CrateCreationService
from features.autonomy.autonomous_developer import develop_from_goal
from shared.logger import getLogger
from will.agents.coder_agent import CoderAgent
from will.agents.execution_agent import _ExecutionAgent
from will.agents.plan_executor import PlanExecutor
from will.orchestration.prompt_pipeline import PromptPipeline

logger = getLogger(__name__)
console = Console()

develop_app = typer.Typer(
    help="AI-native development with constitutional governance",
    no_args_is_help=True,
)


# ID: <will-be-generated-by-dev-sync>
@develop_app.command()
# ID: 3a4577aa-15b0-4db6-a6da-df7c8003cf36
async def feature(
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
    # Get context from admin_cli (it's injected during command setup)
    from body.cli.admin_cli import _context

    if _context is None:
        console.print("[red]Error: Context not initialized[/red]")
        raise typer.Exit(code=1)

    context = _context

    # Get description
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
            f"[bold cyan]Autonomous Feature Development[/bold cyan]\n\n"
            f"Goal: {goal}\n"
            f"Mode: {mode}",
            border_style="cyan",
        )
    )

    # Initialize agents
    prompt_pipeline = PromptPipeline(context.git_service.repo_path)
    plan_executor = PlanExecutor(
        context.file_handler, context.git_service, context.planner_config
    )
    coder_agent = CoderAgent(
        cognitive_service=context.cognitive_service,
        prompt_pipeline=prompt_pipeline,
        auditor_context=context.auditor_context,
    )
    executor_agent = _ExecutionAgent(
        coder_agent=coder_agent,
        plan_executor=plan_executor,
        auditor_context=context.auditor_context,
    )

    # Generate code
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating code with AI agents...", total=None)

        # Use existing autonomous developer
        # In future: modify to return files instead of applying directly
        output_mode = "crate" if mode in ("auto", "manual") else "direct"
        success, result = await develop_from_goal(
            context, goal, executor_agent, output_mode=output_mode
        )

        progress.update(task, completed=True)

    if not success:
        console.print("\n[bold red]✗ Code generation failed[/bold red]")
        console.print(f"Error: {result}")
        raise typer.Exit(code=1)

    # Handle different modes
    if mode == "direct":
        # Old behavior - direct apply
        console.print(
            "\n[bold green]✓ Code generated and applied directly[/bold green]"
        )
        console.print(result)
        return

    # Create intent crate
    console.print("\n[bold]Creating intent crate...[/bold]")

    try:
        crate_service = CrateCreationService()

        # Extract files from result
        # (This assumes develop_from_goal returns dict of files in crate mode)
        files_generated = result.get("files", {})
        generation_metadata = {
            "context_tokens": result.get("context_tokens", 0),
            "generation_tokens": result.get("generation_tokens", 0),
            "validation_passed": True,
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

        # Show files
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
        else:  # manual
            console.print(
                "\n[yellow]Manual mode: Crate created but not submitted for processing.[/yellow]"
            )
            console.print(
                f"Review and process: [cyan]core-admin crate process {crate_id}[/cyan]"
            )

    except Exception as e:
        console.print("\n[bold red]✗ Failed to create crate[/bold red]")
        console.print(f"Error: {e}")
        logger.error(f"Crate creation failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


# ID: <will-be-generated-by-dev-sync>
@develop_app.command()
# ID: ed405581-a4d4-4bf9-8ed6-06861c67ffdc
async def fix(
    description: str = typer.Argument(..., help="Bug description"),
    from_file: Path = typer.Option(None, help="Read description from file"),
    mode: str = typer.Option("auto", help="Mode: auto, manual, or direct"),
):
    """
    Generate bug fix with constitutional compliance.

    Similar to feature command but optimized for fixes.

    Examples:
        poetry run core-admin develop fix "JWT validation fails on expired tokens"
        poetry run core-admin develop fix --from-file bug-report.txt
    """
    # Reuse feature command logic
    await feature(description, from_file, mode)


# ID: <will-be-generated-by-dev-sync>
@develop_app.command()
# ID: 055cc77b-612b-41cc-b7ab-68e593ad795e
async def test(
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
    await feature(goal, None, mode)


# ID: <will-be-generated-by-dev-sync>
@develop_app.command()
# ID: 77fe0f77-fcce-4ddb-91fa-995ccaeb67d9
async def refactor(
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

    await feature(goal, None, mode)


# ID: <will-be-generated-by-dev-sync>
@develop_app.command()
# ID: 8471606d-8f58-4551-90df-4cdb143013db
def info():
    """
    Show information about the autonomous development system.
    """
    console.print(
        Panel.fit(
            "[bold cyan]CORE Autonomous Development System[/bold cyan]\n\n"
            "[bold]Available Commands:[/bold]\n"
            "  • feature   - Generate new features\n"
            "  • fix       - Generate bug fixes\n"
            "  • test      - Generate tests\n"
            "  • refactor  - Perform refactoring\n\n"
            "[bold]Modes:[/bold]\n"
            "  • auto   - Create crate and process automatically (default)\n"
            "  • manual - Create crate but wait for manual processing\n"
            "  • direct - Apply changes immediately (legacy)\n\n"
            "[bold]Process:[/bold]\n"
            "  1. AI agents generate code\n"
            "  2. Constitutional validation\n"
            "  3. Intent crate creation\n"
            "  4. Canary validation (isolated environment)\n"
            "  5. Automatic deployment (if safe)\n\n"
            "[bold]Tracking:[/bold]\n"
            "  core-admin crate status <id>   - Check crate status\n"
            "  core-admin crate list          - List all crates\n"
            "  core-admin daemon logs         - View processing logs",
            border_style="cyan",
        )
    )
