# src/body/cli/resources/admin/hub.py
import typer


app = typer.Typer(
    name="admin",
    help="System forensics: decision traces, refusals, and pattern analytics.",
    no_args_is_help=True,
)
