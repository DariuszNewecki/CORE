# src/cli/resources/law/hub.py
import typer


app = typer.Typer(
    name="law",
    help="Grounded answers about this repository's law, with sources (ADR-168).",
    no_args_is_help=True,
)
