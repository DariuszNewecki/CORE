# src/shared/__init__.py

"""
`shared` — Cross-cutting, foundational building blocks for CORE.

This namespace provides stable, low-level primitives used across the
entire system. Nothing in here depends on features/, agents/, or
domain-specific logic.

Public surface (2.6.0)
----------------------
The following symbols form the published extension contract per
ADR-084 D4 (runtime fork shape). Forks register their own atomic
actions and return these result types:

- ``atomic_action`` — decorator authorizing governed mutations
- ``ActionResult``, ``ActionImpact`` — atomic-action return contract
- ``ComponentResult`` — universal return type for Body components
- ``RefusalResult`` — first-class refusal outcome

Every other symbol in ``shared`` is internal. Future surface
(additional ``__all__`` entries) is gated on ADR-shaped promotions per
ADR-084 D4 and F-48.4.

Sub-packages
------------
- ``shared.utils`` — implementation modules: reusable tools, utilities,
  low-level helpers.
- ``shared.models`` — shared model definitions used by multiple
  subsystems.

Dependency rule
---------------
``shared/`` MAY depend only on the Python standard library and other
modules inside ``shared/``. Nothing outside ``shared/`` may depend on
feature-specific logic.
"""

from __future__ import annotations

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.component_primitive import ComponentResult
from shared.models.refusal_result import RefusalResult


__all__ = [
    "ActionImpact",
    "ActionResult",
    "ComponentResult",
    "RefusalResult",
    "atomic_action",
]
