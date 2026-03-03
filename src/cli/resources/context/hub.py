# src/cli/resources/context/hub.py
import typer


# Stable hub for context resource commands.
# All context commands import from here to avoid circular imports.
app = typer.Typer(
    name="context",
    help="Build and explore context packages for LLM assistance.",
    no_args_is_help=True,
)
