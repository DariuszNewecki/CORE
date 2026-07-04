# src/body/services/capability_tagging_dispatch.py
"""
Body-layer dispatch facade for capability tagging (ADR-064 closure).

Eliminates the body→will import in fix_actions.py by wrapping the
Will-layer main_async callable behind a constructor-injected interface.
The composition root (service_registry / daemon.py) wires the callable in;
Body code only sees this facade — no will.* import exists in this file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: cefb3f05-1385-45ce-be5a-276706326951
class CapabilityTaggingService:
    """Body-layer facade for the Will-owned capability tagger (ADR-064 Option A).

    The Will-layer ``main_async`` callable is injected at construction so
    Body callers never import from ``will.*`` directly.  Service wiring
    happens at the composition root (``service_registry`` for the API path,
    ``daemon.py`` for the daemon path).
    """

    def __init__(self, main_async_fn: Callable[..., Any]) -> None:
        self._fn = main_async_fn

    # ID: 0e9e9656-ca20-4d27-ac5c-b53d1dd791ac
    async def run(
        self,
        *,
        session_factory: Any,
        cognitive_service: CognitiveService,
        knowledge_service: KnowledgeService,
        write: bool = False,
        dry_run: bool = False,
        limit: int = 0,
    ) -> None:
        """Delegate to the injected will-layer main_async callable."""
        await self._fn(
            session_factory=session_factory,
            cognitive_service=cognitive_service,
            knowledge_service=knowledge_service,
            write=write,
            dry_run=dry_run,
            limit=limit,
        )
