# src/system/tools/models.py
"""
Lightweight, JSON-safe data models for code-introspection tooling.

Why this exists:
- Keep all graph/export structures strictly JSON-serializable.
- Avoid non-JSON-native types like `set`, `Path`, or custom objects in public fields.
- Provide `to_dict()` helpers that are stable for downstream writers (reports, graphs).

Key fix in this file:
- `FunctionInfo.calls` is a **List[str]** (not a set). Lists are JSON-safe and
  preserve order; we deduplicate on write to keep outputs tidy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


def _dedupe_seq(seq: List[str]) -> List[str]:
    """Deduplicate while preserving order (stable for reports/JSON)."""
    return list(dict.fromkeys(seq))


@dataclass
class FunctionInfo:
    """
    Minimal, JSON-safe representation of a function for graphing and reports.
    """

    # Identity
    name: str
    qualname: str
    module: str

    # Source
    filepath: str
    lineno: int
    end_lineno: Optional[int] = None

    # Signature / docs
    params: Dict[str, Optional[str]] = field(
        default_factory=dict
    )  # {param_name: annotation or None}
    returns: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    base_classes: List[str] = field(default_factory=list)
    entry_point_type: Optional[str] = None
    entry_point_justification: Optional[str] = None
    structural_hash: Optional[str] = None

    # Relations / metrics
    calls: List[str] = field(default_factory=list)  # 👈 JSON-safe (list), not a set
    complexity: Optional[int] = None  # cyclomatic or similar, optional

    # Misc
    type: Optional[str] = None  # Added to handle function type
    tags: List[str] = field(default_factory=list)  # free-form labels, optional

    def add_call(self, callee_qualname: str) -> None:
        """Record a call edge (duplicates are ok; they are deduped at export)."""
        if not isinstance(callee_qualname, str):
            return
        self.calls.append(callee_qualname)

    def add_tag(self, tag: str) -> None:
        if isinstance(tag, str) and tag:
            self.tags.append(tag)

    def to_dict(self) -> Dict:
        """
        JSON-stable dict. Ensures lists are de-duplicated and primitives only.
        """
        data = asdict(self)
        data["calls"] = _dedupe_seq([str(x) for x in (self.calls or [])])
        data["decorators"] = _dedupe_seq([str(x) for x in (self.decorators or [])])
        data["tags"] = _dedupe_seq([str(x) for x in (self.tags or [])])
        data["base_classes"] = _dedupe_seq([str(x) for x in (self.base_classes or [])])

        # Normalize params to {name: annotation or None}, all strings
        params_norm: Dict[str, Optional[str]] = {}
        for k, v in (self.params or {}).items():
            key = str(k)
            params_norm[key] = None if v is None else str(v)
        data["params"] = params_norm

        # Ensure primitives for optional fields
        data["returns"] = None if self.returns is None else str(self.returns)
        data["docstring"] = None if self.docstring is None else str(self.docstring)
        data["module"] = str(self.module)
        data["name"] = str(self.name)
        data["qualname"] = str(self.qualname)
        data["filepath"] = str(self.filepath)
        data["lineno"] = int(self.lineno)
        if self.end_lineno is not None:
            data["end_lineno"] = int(self.end_lineno)
        else:
            data["end_lineno"] = None
        if self.complexity is not None:
            data["complexity"] = int(self.complexity)
        else:
            data["complexity"] = None
        data["type"] = None if self.type is None else str(self.type)  # Added for type

        return data


@dataclass
class ModuleInfo:
    """
    Aggregate of functions from a single Python module (file).
    """

    module: str
    filepath: str
    functions: List[FunctionInfo] = field(default_factory=list)

    def add_function(self, fn: FunctionInfo) -> None:
        if isinstance(fn, FunctionInfo):
            self.functions.append(fn)

    def to_dict(self) -> Dict:
        return {
            "module": str(self.module),
            "filepath": str(self.filepath),
            "functions": [f.to_dict() for f in self.functions],
        }


@dataclass
class ImportEdge:
    """
    Simple import edge (module-level), used by guards/graph builders.
    """

    importer: str  # e.g., "core.services.foo"
    imported: str  # e.g., "shared.utils.time"
    lineno: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "importer": str(self.importer),
            "imported": str(self.imported),
            "lineno": None if self.lineno is None else int(self.lineno),
        }


__all__ = [
    "FunctionInfo",
    "ModuleInfo",
    "ImportEdge",
]
