# src/body/cli/resources/vectors/hub.py
import typer


app = typer.Typer(
    name="vectors",
    help="Vector store operations (Qdrant).",
    no_args_is_help=True,
)
