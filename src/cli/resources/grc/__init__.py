# src/cli/resources/grc/__init__.py
"""GRC (Governance, Risk, Compliance) gap-analysis commands."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="grc",
    help="Compliance gap-analysis: check a document corpus against a requirements catalog.",
    no_args_is_help=True,
)

from . import (
    gap_analysis,  # registers the gap-analysis command on `app`
    ingest,  # registers the ingest command on `app`
)


__all__ = ["app"]
