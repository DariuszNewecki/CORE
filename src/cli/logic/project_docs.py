# src/cli/logic/project_docs.py
"""
CLI wrapper for generating capability documentation.
It reuses the existing Python module entrypoint to keep one source of truth.
"""
from __future__ import annotations

import runpy
import sys

import typer


# ID: 752ead32-df2a-48c5-bb30-3530397e2cd2
def docs(output: str = "docs/10_CAPABILITY_REFERENCE.md") -> None:
    """
    Generate capability documentation into the given output path.
    """
    mod = "features.introspection.generate_capability_docs"
    # Preserve original argv and invoke the module as if run with: python -m ... --output <path>
    argv_backup = sys.argv[:]
    try:
        sys.argv = [mod, "--output", output]
        runpy.run_module(mod, run_name="__main__")
    finally:
        sys.argv = argv_backup
    typer.echo(f"📚 Capability documentation written to: {output}")
