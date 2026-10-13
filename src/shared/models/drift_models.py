# src/shared/models/drift_models.py
"""
Defines the Pydantic/dataclass models for representing capability drift.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.utils.dataclass_dict import DataclassDict


@dataclass
# ID: a8f4575c-a899-4dde-9d8f-c2825eaa7259
class DriftReport(DataclassDict):
    """A structured report of the drift between manifest and code."""

    missing_in_code: list[str]
    undeclared_in_manifest: list[str]
    mismatched_mappings: list[dict]
