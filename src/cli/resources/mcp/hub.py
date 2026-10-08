# src/cli/resources/mcp/hub.py
import typer


app = typer.Typer(
    name="mcp",
    help="The assistant surface over MCP: law, decisions and verdict for any AI assistant (ADR-168).",
    no_args_is_help=True,
)
