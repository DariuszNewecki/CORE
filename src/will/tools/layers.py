# src/will/tools/layers.py

"""
Architectural layer definitions for CORE's Mind-Body-Will structure.
"""

from __future__ import annotations


LAYERS = {
    "mind": "Constitutional governance, policies, and validation rules",
    "body": "Pure execution - CLI commands, actions, no decision-making",
    "will": "Autonomous agents and AI decision-making",
    "services": "Infrastructure orchestration with external systems (DB, APIs, caches)",
    "shared": "Pure utilities with no external dependencies or state",
    "domain": "Business logic and domain rules without external dependencies",
    "features": "High-level capabilities combining domain + services",
    "core": "Action handlers for autonomous operations",
}


# ID: ee821e06-e7b9-4ab7-8529-c7a1ad58adb2
def get_layer_purpose(layer_name: str) -> str:
    """Get the purpose description for a layer."""
    return LAYERS.get(layer_name, "Unknown layer")


# ID: 9d3f6ef5-1983-4d3a-8a24-fdab3023e72c
def get_all_layers() -> dict[str, str]:
    """Get all layer definitions."""
    return LAYERS.copy()
