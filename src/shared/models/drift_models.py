# src/shared/models/drift_models.py
"""
Defines the Pydantic/dataclass models for representing capability drift.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List


@dataclass
# ID: a8f4575c-a899-4dde-9d8f-c2825eaa7259
class DriftReport:
    """A structured report of the drift between manifest and code."""

    missing_in_code: List[str]
    undeclared_in_manifest: List[str]
    mismatched_mappings: List[Dict]

    # ID: 9db89268-07cb-4bf7-9abe-14df2f0aae8a
    def to_dict(self) -> Dict[str, Any]:
        """Serializes the report to a dictionary."""
        return asdict(self)
