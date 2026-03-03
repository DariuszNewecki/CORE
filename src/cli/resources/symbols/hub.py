# src/cli/resources/symbols/hub.py

import typer


# Stable hub for symbols resource commands
app = typer.Typer(
    name="symbols",
    help="Operations for the symbol registry and Knowledge Graph identification.",
    no_args_is_help=True,
)
