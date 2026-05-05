# src/cli/resources/intent/hub.py
import typer


app = typer.Typer(
    name="intent",
    help="Constitutional intent operations (.intent/ projections).",
    no_args_is_help=True,
)
