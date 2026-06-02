# src/will/__init__.py
"""
`will` — Autonomous developer and autonomy orchestration.

Will-layer components (workers, agents, strategists, phases) are
internal engine machinery. Forks extend CORE via ``@atomic_action``
(see ``shared``) or via the sensor/action interfaces declared by
F-41/F-42/F-43 — not by importing Will-layer symbols directly. No
symbols are re-exported for 2.6.0; future surface is gated on
ADR-shaped promotions per ADR-084 D4 and F-48.4.
"""

from __future__ import annotations


__all__: list[str] = []
