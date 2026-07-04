# src/will/tools/context/standards.py
"""Re-export stub — implementation moved to shared.tools per ADR-063."""

from __future__ import annotations

from shared.tools.context.standards import (
    LAYER_PURPOSES,
    get_anti_patterns,
    get_layer_patterns,
    get_typical_deps,
)


__all__ = [
    "LAYER_PURPOSES",
    "get_anti_patterns",
    "get_layer_patterns",
    "get_typical_deps",
]
