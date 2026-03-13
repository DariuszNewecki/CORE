# src/cli/commands/interactive_test.py
"""
Interactive test generation command.
... (docstring remains the same)
"""

from __future__ import annotations

import typer

from cli.logic.interactive_test_logic import run_interactive_test_generation
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta


logger = getLogger(__name__)
app = typer.Typer(
    help="Interactive test generation with step-by-step approval", no_args_is_help=True
)


@app.command("generate")
@command_meta(
    canonical_name="interactive-test.generate",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    summary="Generate tests interactively with step-by-step prompts.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: fbc18275-df5e-426a-b39e-78eea4048069
async def generate_interactive(
    ctx: typer.Context,
    target: str = typer.Argument(
        ...,
        help="Module path to generate tests for (e.g., src/shared/models/knowledge.py)",
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually execute the final creation of the test file."
    ),
):
    """
    Generate tests interactively with step-by-step prompts.
    ... (docstring remains the same)
    """
    core_context: CoreContext = ctx.obj
    logger.info("=" * 80)
    logger.info("🎯 Interactive Test Generation: %s", target)
    logger.info("=" * 80)
    try:
        success = await run_interactive_test_generation(
            target_file=target, core_context=core_context
        )
        if not success:
            logger.warning("Interactive test generation cancelled by user")
            raise typer.Exit(code=1)
        logger.info("✅ Interactive test generation completed successfully")
    except Exception as e:
        logger.error("❌ Interactive test generation failed: %s", e, exc_info=True)
        raise typer.Exit(code=1)


@app.command("info")
@command_meta(
    canonical_name="interactive-test.info",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Display information about the interactive test generation workflow.",
    dangerous=False,
)
# ID: f9dec947-696f-4f69-8892-567aa2fe4f4d
def info():
    """Show information about interactive test generation."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    logger.info(
        Panel.fit(
            "[bold cyan]Interactive Test Generation[/bold cyan]\n\n[bold]Purpose:[/bold]\nGenerate tests with full visibility and control at each step.\n\n[bold]Features:[/bold]\n  • Step-by-step prompts and approval\n  • Code preview with syntax highlighting\n  • Edit at any step with $EDITOR\n  • Skip ahead or cancel anytime\n  • All artifacts saved to work/interactive/\n  • Complete decision log maintained\n\n[bold]Steps:[/bold]\n  1. [cyan]Generate[/cyan] - LLM creates test code\n  2. [cyan]Auto-heal[/cyan] - Fix imports, headers, format\n  3. [cyan]Audit[/cyan] - Constitutional governance check\n  4. [cyan]Canary[/cyan] - Optional sandbox trial\n  5. [cyan]Execute[/cyan] - Create the test file\n\n[bold]Usage:[/bold]\n  core-admin interactive-test generate <module-path>",
            border_style="cyan",
        )
    )
