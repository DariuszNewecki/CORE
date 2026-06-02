# src/api/__init__.py
"""
`api` — FastAPI routes and dependency providers.

The public surface of ``api`` is the HTTP API governed by ADR-087, not
Python imports. No symbols are re-exported from this package — consumers
integrate via HTTP, not via ``from api import ...``.

Future surface (additional `__all__` entries) is gated on ADR-shaped
promotions per ADR-084 D4 (runtime fork shape) and F-48.4.
"""

from __future__ import annotations


__all__: list[str] = []
