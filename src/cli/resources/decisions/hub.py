# src/cli/resources/decisions/hub.py
import typer


app = typer.Typer(
    name="decisions",
    help="Decision history: the repository's ADRs, with their files (ADR-168).",
    no_args_is_help=True,
)
