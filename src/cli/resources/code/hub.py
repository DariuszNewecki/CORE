# src/cli/resources/code/hub.py
import typer


# This is the "Stable Hub" that everyone can import without circular risk
app = typer.Typer(
    name="code",
    help=(
        "Codebase quality, style, and verification operations; "
        "`code audit --offline` needs no services."
    ),
    no_args_is_help=True,
)
