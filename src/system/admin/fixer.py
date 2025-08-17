# src/system/admin/fixer.py
"""
Intent: Registers self-healing and code-fixing tools with the CORE Admin CLI.
"""

import typer

from system.tools.docstring_adder import fix_missing_docstrings


def register(app: typer.Typer) -> None:
    """Intent: Register fixer commands under the admin CLI."""
    fixer_app = typer.Typer(help="Self-healing and code quality tools.")
    app.add_typer(fixer_app, name="fix")

    fixer_app.command("docstrings")(fix_missing_docstrings)
