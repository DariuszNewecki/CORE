# src/cli/resources/mcp/hub.py
import typer


app = typer.Typer(
    name="mcp",
    help="The assistant surface over MCP: law, decisions and verdict for any AI assistant.",
    no_args_is_help=True,
)
