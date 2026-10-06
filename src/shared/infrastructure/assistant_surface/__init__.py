# src/shared/infrastructure/assistant_surface/__init__.py

"""The assistant surface's shared core (ADR-168 D2, amendment 2026-10-06).

One implementation behind every face (CLI, MCP, later API), so that every
producer gets the same answers. Read-only and deterministic: no database, no
LLM, no writes.
"""

from __future__ import annotations
