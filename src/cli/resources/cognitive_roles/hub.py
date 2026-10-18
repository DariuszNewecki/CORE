# src/cli/resources/cognitive_roles/hub.py
import typer


app = typer.Typer(
    name="cognitive-roles",
    help="Cognitive-role capability projection.",
    no_args_is_help=True,
)
