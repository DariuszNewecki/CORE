# src/will/tools/context/standards.py

"""Constitutional rules of thumb for architectural layers."""

from __future__ import annotations


LAYER_PURPOSES = {
    "mind": "Constitutional governance, policies, and validation rules",
    "body": "Pure execution - CLI commands, actions, no decision-making",
    "will": "Autonomous agents and AI decision-making",
    "services": "Infrastructure orchestration (DB, APIs, caches)",
    "shared": "Pure utilities with no external dependencies",
    "tests": "Comprehensive behavior validation",
}


# ID: d61977b9-7f28-41db-985b-c21c75ed2ada
def get_layer_patterns(layer: str) -> list[str]:
    patterns = {
        "shared": ["Pure utilities", "No side effects"],
        "core": ["Atomic Actions", "Strict Result Contract", "Governed Mutations"],
        "will": ["Planning", "Orchestration", "Decision Making"],
        "tests": ["Comprehensive coverage", "Use fixtures for setup"],
    }
    return patterns.get(layer, [])


# ID: 6cb503ab-570b-4a66-8d3f-5ee367e7c668
def get_typical_deps(layer: str) -> list[str]:
    deps = {
        "shared": [
            "from __future__ import annotations",
            "from shared.logger import getLogger",
        ],
        "core": [
            "from body.atomic.registry import register_action",
            "from shared.action_types import ActionResult",
        ],
        "will": ["from shared.models import ExecutionTask"],
        "tests": ["import pytest", "from sqlalchemy.orm import Session"],
    }
    return deps.get(layer, [])


# ID: 180997be-53d6-415f-8bcd-63a31c4f22ed
def get_anti_patterns(layer: str) -> list[str]:
    anti = {
        "core": ["DO NOT make autonomous decisions", "MUST return ActionResult"],
        "will": ["DO NOT implement action execution", "DO NOT bypass Gateway"],
        "tests": ["DO NOT import from src. prefix", "DO NOT hallucinate models"],
    }
    return anti.get(layer, [])
