# src/body/cli/commands/interactive_test.py

"""
Interactive test generation command.

Provides step-by-step visibility and control over autonomous test generation.
Each phase pauses for user review and approval.

Constitutional Compliance:
- Separation of Concerns: Separate command, not added to existing command
- Async-safe: Uses asyncio.subprocess, not blocking subprocess.run()
- Proper imports: All dependencies explicitly imported
- Single Responsibility: One command, one purpose
"""

from __future__ import annotations

import typer

from body.cli.logic.interactive_test_logic import run_interactive_test_generation
from shared.cli_utils import async_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)

app = typer.Typer(
    help="Interactive test generation with step-by-step approval",
    no_args_is_help=True,
)


@app.command("generate")
@async_command
# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
async def generate_interactive(
    ctx: typer.Context,
    target: str = typer.Argument(
        ...,
        help="Module path to generate tests for (e.g., src/shared/models/knowledge.py)",
    ),
):
    """
    Generate tests interactively with step-by-step prompts.

    This command provides full visibility into the test generation process:
    1. Generate code (with LLM)
    2. Auto-heal code (fix imports, headers, format)
    3. Constitutional audit
    4. Canary trial (optional)
    5. Execute (create file)

    At each step, you can:
    - Review the code
    - Edit manually
    - Skip ahead
    - Cancel

    All artifacts are saved to work/interactive/{timestamp}/ for review.

    Example:
        core-admin interactive-test generate src/shared/infrastructure/database/models/knowledge.py
    """
    core_context: CoreContext = ctx.obj

    logger.info("=" * 80)
    logger.info("🎯 Interactive Test Generation: %s", target)
    logger.info("=" * 80)

    try:
        success = await run_interactive_test_generation(
            target_file=target,
            core_context=core_context,
        )

        if not success:
            logger.warning("Interactive test generation cancelled by user")
            raise typer.Exit(code=1)

        logger.info("✅ Interactive test generation completed successfully")

    except Exception as e:
        logger.error("❌ Interactive test generation failed: %s", e, exc_info=True)
        raise typer.Exit(code=1)


@app.command("info")
# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
def info():
    """Show information about interactive test generation."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(
        Panel.fit(
            "[bold cyan]Interactive Test Generation[/bold cyan]\n\n"
            "[bold]Purpose:[/bold]\n"
            "Generate tests with full visibility and control at each step.\n\n"
            "[bold]Features:[/bold]\n"
            "  • Step-by-step prompts and approval\n"
            "  • Code preview with syntax highlighting\n"
            "  • Edit at any step with $EDITOR\n"
            "  • Skip ahead or cancel anytime\n"
            "  • All artifacts saved to work/interactive/\n"
            "  • Complete decision log maintained\n\n"
            "[bold]Steps:[/bold]\n"
            "  1. [cyan]Generate[/cyan] - LLM creates test code\n"
            "  2. [cyan]Auto-heal[/cyan] - Fix imports, headers, format\n"
            "  3. [cyan]Audit[/cyan] - Constitutional governance check\n"
            "  4. [cyan]Canary[/cyan] - Optional sandbox trial\n"
            "  5. [cyan]Execute[/cyan] - Create the test file\n\n"
            "[bold]Usage:[/bold]\n"
            "  core-admin interactive-test generate <module-path>",
            border_style="cyan",
        )
    )
