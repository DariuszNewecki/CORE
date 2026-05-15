# src/shared/protocols/brain_services.py

"""
Brain Services Provider Protocol.

Defines the interface for resolving cognitive_service and qdrant_service
at runtime. Allows shared-layer infrastructure (notably ContextService)
to delegate service resolution without importing directly from body or
will. The body's ServiceRegistry structurally satisfies this protocol.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
# ID: 50fefd28-6dcb-4105-8c9c-973a9bdb2100
class BrainServicesProvider(Protocol):
    """
    Structural interface for the runtime service resolver.

    Implementations expose lazy async getters for the cognitive and vector
    services so callers can defer resolution past sync construction boundaries.
    """

    # ID: 97faba28-2ce5-4d35-8c70-a00f3f0d17b6
    async def get_cognitive_service(self) -> Any:
        """Return the initialized cognitive service instance."""
        ...

    # ID: 075d81b3-40b2-4431-ac99-381e3fb1ecc8
    async def get_qdrant_service(self) -> Any:
        """Return the initialized vector (Qdrant) service instance."""
        ...
