# src/cli/resources/secrets/hub.py
import typer


app = typer.Typer(
    name="secrets",
    help="Manage encrypted secrets in the database.",
    no_args_is_help=True,
)
