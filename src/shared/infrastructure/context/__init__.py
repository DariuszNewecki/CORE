# src/shared/infrastructure/context/__init__.py

"""Context Package Service.

Constitutional governance for all LLM context.
Enforces schema validation, privacy policies, and resource constraints.

Key components:
- ContextService: Main orchestrator (use this!)
- ContextBuilder: Assembles governed context packets
- Validator: Enforces schema.yaml compliance
- Redactor: Applies policy.yaml rules
- Serializers: YAML I/O and token estimation
- Cache: Hash-based packet caching
- Database: Metadata persistence

Usage:
    from shared.infrastructure.context import ContextService

    service = ContextService(db, qdrant, config)
    packet = await service.build_for_task(task_spec)
"""

from __future__ import annotations

from .builder import ContextBuilder
from .cache import ContextCache
from .database import ContextDatabase
from .redactor import ContextRedactor
from .serializers import ContextSerializer
from .service import ContextService
from .validator import ContextValidator


__all__ = [
    "ContextBuilder",
    "ContextCache",
    "ContextDatabase",
    "ContextRedactor",
    "ContextSerializer",
    "ContextService",  # Main entry point
    "ContextValidator",
]

__version__ = "0.2.0"
