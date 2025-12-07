# src/services/vector/adapters/__init__.py

"""
Domain Adapters for Vector Indexing

Adapters translate domain-specific data formats into VectorizableItems
for the unified VectorIndexService.

Available Adapters:
- ConstitutionalAdapter: Policies and patterns (YAML)
- ModuleAnchorAdapter: Architectural module context (coming in Step 3)
- CapabilityAdapter: Knowledge graph symbols (coming in Step 4)
"""

from __future__ import annotations

from .constitutional_adapter import ConstitutionalAdapter


__all__ = ["ConstitutionalAdapter"]
