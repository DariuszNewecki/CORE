# src/shared/__init__.py

"""
`shared` — Cross-cutting, foundational building blocks for CORE.

This namespace provides *stable, low-level primitives* used across the
entire system. Nothing in here depends on features/, agents/, or domain-
specific logic.

Sub-packages include:

- shared.universal
    Canonical micro-helpers for reuse-first development.

- shared.utils
    Implementation modules providing reusable tools, utilities, and
    low-level helpers. `shared.universal` re-exports a curated,
    stable surface from here.

- shared.models
    Simple, shared model definitions used by multiple subsystems.

Dependency rule:
    shared/ MAY depend only on the Python standard library and other
    modules inside shared/. Nothing outside shared/ may depend on
    feature-specific logic.

This guarantees a stable, well-defined reuse surface for CoderAgent and
ContextPackage reuse analysis.
"""

from __future__ import annotations
