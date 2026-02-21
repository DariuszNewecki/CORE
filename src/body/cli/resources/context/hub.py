# src/body/cli/resources/context/hub.py
import typer


# This is the "Stable Hub" that everyone can import without circular risk
app = typer.Typer(
    name="code",
    help="Codebase quality, style, and verification operations.",
    no_args_is_help=True,
)
