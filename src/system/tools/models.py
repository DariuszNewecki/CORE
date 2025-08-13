# src/system/tools/models.py
"""
Data models and shared structures for the system's tooling.
This module exists to prevent circular import dependencies.
"""
from dataclasses import dataclass, field
from typing import Set, Optional, List

@dataclass
class FunctionInfo:
    """A data structure holding all analyzed information about a single symbol (function, method, or class)."""
    key: str
    name: str
    type: str
    file: str
    domain: str
    agent: str
    capability: str
    intent: str
    docstring: Optional[str]
    calls: Set[str] = field(default_factory=set)
    line_number: int = 0
    is_async: bool = False
    parameters: List[str] = field(default_factory=list)
    entry_point_type: Optional[str] = None
    last_updated: str = ""
    is_class: bool = False
    base_classes: List[str] = field(default_factory=list)
    entry_point_justification: Optional[str] = None
    parent_class_key: Optional[str] = None
    structural_hash: str = ""