# src/body/__init__.py
"""
`body` — Analyzers, actors, infrastructure workers. The execution layer.

Body components are internal engine machinery. The extension contract
for forks (atomic actions, result types) lives in ``shared`` — not
here. No symbols are re-exported for 2.6.0; future surface is gated on
ADR-shaped promotions per ADR-084 D4 and F-48.4.
"""

from __future__ import annotations


__all__: list[str] = []
