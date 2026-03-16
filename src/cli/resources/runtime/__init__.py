# src/cli/resources/runtime/__init__.py
"""Runtime resource — live state and health of the running CORE system."""

from __future__ import annotations

from .health import runtime_app


app = runtime_app
