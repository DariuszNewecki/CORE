# src/cli/resources/dev/hub.py

import typer


# This hub allows sub-commands to import the app without creating a circular loop
app = typer.Typer(
    name="dev",
    help="High-level developer workflows: synchronization, AI chat, and stability tools.",
    no_args_is_help=True,
)
