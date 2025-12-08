# src/api/cli_user.py
"""
End-user conversational interface to CORE.

This module provides the 'core' CLI binary for end users who want to
interact with CORE conversationally without needing to understand
internal commands or architecture.

Constitutional boundaries:
- All operations route through ConversationalAgent (Will layer)
- All proposals validated by Mind governance
- All execution via Body atomic actions
"""

import asyncio

import typer

from shared.logger import getLogger


logger = getLogger(__name__)

app = typer.Typer(
    name="core",
    help="Chat with CORE about your codebase",
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    message: str = typer.Argument(None, help="Your message to CORE"),
):
    """
    Talk to CORE conversationally.

    Examples:
        core "analyze the CoreContext class"
        core "what does ContextBuilder do?"
        core "my tests are failing"
        core "refactor this file for clarity"
    """
    if ctx.invoked_subcommand is not None:
        # A subcommand was invoked, let it handle
        return

    if not message:
        print("Usage: core <message>")
        print('Example: core "what does ContextBuilder do?"')
        raise typer.Exit(1)

    logger.info(f"User message: {message}")

    # Run async handler
    try:
        asyncio.run(handle_message(message))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        raise typer.Exit(130)
    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        raise typer.Exit(1)


async def handle_message(message: str) -> None:
    """
    Async handler for user messages.

    Initializes ConversationalAgent and processes the message.

    Args:
        message: User's natural language query
    """
    from will.agents.conversational_agent import create_conversational_agent

    print("🤖 CORE is thinking...\n")

    # Create agent with all dependencies
    agent = await create_conversational_agent()

    # Process message
    response = await agent.process_message(message)

    # Display response
    print("─" * 70)
    print(response)
    print("─" * 70)
    print()


if __name__ == "__main__":
    app()
