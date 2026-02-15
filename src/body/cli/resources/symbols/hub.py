# src/body/cli/resources/symbols/hub.py
# ID: a7c3e9f1-b2d4-4f6a-8e0c-1d3b5a7f9e2c

import typer


# Stable hub for symbols resource commands
app = typer.Typer(
    name="symbols",
    help="Operations for the symbol registry and Knowledge Graph identification.",
    no_args_is_help=True,
)
