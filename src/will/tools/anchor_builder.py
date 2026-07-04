# src/will/tools/anchor_builder.py
"""Re-export stub — implementation moved to shared.tools per ADR-063."""

from __future__ import annotations

from shared.tools.anchor_builder import (
    build_layer_anchor,
    build_module_anchor,
    get_layer_description_for_embedding,
    get_module_description_for_embedding,
)


__all__ = [
    "build_layer_anchor",
    "build_module_anchor",
    "get_layer_description_for_embedding",
    "get_module_description_for_embedding",
]
