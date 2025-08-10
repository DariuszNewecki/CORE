# src/system/admin_cli.py
"""
Intent: Stable public entrypoint for the CORE Admin CLI.
Re-exports the Typer application without exposing internal wiring.
"""
from system.admin import app

__all__ = ["app"]
