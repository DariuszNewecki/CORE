# src/shared/lifecycles/__init__.py
"""Shared lifecycle enumerations — pure data, no layer dependencies.

Per ADR-062: lifecycle state enums that are referenced across layer
boundaries (e.g. Body atomic actions referencing Will-owned domain
concepts) live here so the cross-layer import is eliminated.
"""

from __future__ import annotations

from shared.lifecycles.proposal import ProposalStatus


__all__ = ["ProposalStatus"]
