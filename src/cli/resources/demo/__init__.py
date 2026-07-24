# src/cli/resources/demo/__init__.py
"""
Demo Resource — isolated, opt-in demonstrations that CORE governs its own changes.

Commands:
- consequence-chain : run the genuine, isolated governance consequence chain (ADR-155)
- cleanup           : remove a retained isolated-demo workspace by run id
"""

from __future__ import annotations

# Register the neurons (import triggers @app.command decorators)
from . import cleanup, consequence_chain

# Stable hub first
from .hub import app


__all__ = ["app"]
