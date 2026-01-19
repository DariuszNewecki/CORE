# src/will/tools/context/models.py

"""Refactored logic for src/will/tools/context/models.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
# ID: bdd8bfc9-395f-4c41-b42a-280836600391
class CodeExample:
    file_path: str
    symbol_name: str
    code_snippet: str
    purpose: str
    similarity_score: float


@dataclass
# ID: a40e6bd4-8191-4a81-ad16-22306a6ab801
class ArchitecturalContext:
    goal: str
    target_layer: str
    layer_purpose: str
    layer_patterns: list[str]
    relevant_policies: list[dict[str, Any]]
    placement_confidence: str
    best_module_path: str
    placement_score: float
    similar_examples: list[CodeExample] = field(default_factory=list)
    typical_dependencies: list[str] = field(default_factory=list)
    placement_reasoning: str = ""
    common_patterns_in_module: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    target_file_content: str | None = None
    target_file_path: str | None = None
