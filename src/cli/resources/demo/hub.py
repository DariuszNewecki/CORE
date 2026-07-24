# src/cli/resources/demo/hub.py

import typer


# Stable hub so sub-command modules can import the app without a circular loop
# (mirrors cli/resources/dev/hub.py). ADR-155 Phase 3 public surface.
app = typer.Typer(
    name="demo",
    help="Isolated, opt-in demonstrations that CORE governs its own changes.",
    no_args_is_help=True,
)
