# src/body/cli/resources/dev/hub.py
# ID: 93510675-6c6f-4b5a-8028-ba8f1b5a5b81

import typer


# This hub allows sub-commands to import the app without creating a circular loop
app = typer.Typer(
    name="dev",
    help="High-level developer workflows: synchronization, AI chat, and stability tools.",
    no_args_is_help=True,
)
