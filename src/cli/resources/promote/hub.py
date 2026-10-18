# src/cli/resources/promote/hub.py
from __future__ import annotations

import typer


app = typer.Typer(
    name="promote",
    help="Promotions: main's commits the governor approves to run live (ADR-171).",
    no_args_is_help=True,
)
