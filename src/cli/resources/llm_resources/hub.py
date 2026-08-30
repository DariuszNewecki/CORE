# src/cli/resources/llm_resources/hub.py
import typer


app = typer.Typer(
    name="llm-resources",
    help="core.llm_resources authoring/validation surface (#821 Unit 3).",
    no_args_is_help=True,
)
