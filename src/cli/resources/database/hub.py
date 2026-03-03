# src/cli/resources/database/hub.py

import typer


# Stable hub for database resource commands
app = typer.Typer(
    name="database",
    help="PostgreSQL state and operational data management.",
    no_args_is_help=True,
)
