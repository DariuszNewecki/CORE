# src/cli/resources/llm_resources/hub.py
import typer


app = typer.Typer(
    name="llm-resources",
    help="core.llm_resources authoring/validation surface.",
    no_args_is_help=True,
)
