# src/body/cli/logic/build.py
"""
Registers and implements the 'build' command group for generating
artifacts from the database or constitution.
"""

from __future__ import annotations

import typer

from features.introspection.generate_capability_docs import (
    main as generate_capability_docs,
)

build_app = typer.Typer(
    help="Commands to build artifacts (e.g., documentation) from the database."
)
build_app.command(
    "capability-docs",
    help="Generate the capability reference documentation from the DB.",
)(generate_capability_docs)
