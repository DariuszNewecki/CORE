# src/cli/resources/workers/__init__.py
"""Workers resource — constitutional worker management commands."""

from __future__ import annotations

import typer

from .run import workers_app


app = workers_app
