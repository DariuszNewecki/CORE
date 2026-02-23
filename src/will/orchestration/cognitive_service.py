# src/will/orchestration/cognitive_service.py

"""
CognitiveService - Will-facing facade for cognitive access.

HEALED (V2.3.0):
- JIT Secret Retrieval: Added session_factory to handle encrypted secret
  decryption even after the main initialization session is detached.
- Prevents "Database session has been detached" errors during vectorization.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.services.mind_state_service import MindStateService
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.models import LlmResource
from shared.infrastructure.llm.client import LLMClient
from shared.infrastructure.llm.providers.base import AIProvider
from shared.infrastructure.llm.providers.ollama import OllamaProvider
from shared.infrastructure.llm.providers.openai import OpenAIProvider
from shared.logger import getLogger
from will.agents.cognitive_orchestrator import CognitiveOrchestrator


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from shared.infrastructure.clients.qdrant_client import QdrantService

logger = getLogger(__name__)


# ID: 507c1d3a-e014-4695-a5c6-2e50f2d8dd4d
class CognitiveService:
    """Facade for cognitive operations (clients + embeddings)."""

    def __init__(
        self,
        repo_path: Path,
        qdrant_service: QdrantService | None = None,
        session_factory: Any | None = None,  # ADDED: Support for JIT connections
    ) -> None:
        self._repo_path = Path(repo_path)
        self._qdrant_service = qdrant_service
        self._session_factory = session_factory  # ADDED

        self._init_lock = asyncio.Lock()
        self._loaded = False

        self._config: ConfigService | None = None
        self._mind_state: MindStateService | None = None
        self._orch: CognitiveOrchestrator | None = None

    @property
    # ID: 72526c1d-ff38-4213-a8d1-0c25880dcdc7
    def qdrant_service(self) -> QdrantService:
        if self._qdrant_service is None:
            raise RuntimeError("QdrantService was not injected into CognitiveService.")
        return self._qdrant_service

    # ID: 68895785-8f99-4c02-9167-7191e35a0a98
    async def initialize(self, session: AsyncSession) -> None:
        """Initialize using an explicit AsyncSession (owned by Body)."""
        async with self._init_lock:
            if self._loaded:
                return

            # 1. Load configuration and state using the provided session
            self._config = await ConfigService.create(session)
            self._mind_state = MindStateService(session)

            # 2. Initialize orchestrator
            self._orch = CognitiveOrchestrator(
                repo_path=self._repo_path,
                mind_state_service=self._mind_state,
                provider_factory=self._create_provider_for_resource,
            )
            await self._orch.initialize()

            # 3. CONSTITUTIONAL CLEANUP: Release the session reference.
            if self._config:
                self._config.detach()
            if self._mind_state:
                self._mind_state.detach()

            self._loaded = True
            logger.info("CognitiveService initialized and connections detached.")

    def _require_ready(self) -> None:
        if not self._loaded or not self._orch or not self._config:
            raise RuntimeError("CognitiveService is not initialized.")

    # ID: aec81806-c12d-4f9c-9ca0-d159f3c124ff
    async def _create_provider_for_resource(self, resource: LlmResource) -> AIProvider:
        self._require_ready()
        assert self._config is not None

        prefix = (resource.env_prefix or "").strip().upper()
        if not prefix:
            raise ValueError(f"Resource '{resource.name}' is missing env_prefix.")

        # Note: ConfigService.get works after detach because it uses an internal cache.
        api_url = await self._config.get(f"{prefix}_API_URL")
        model_name = await self._config.get(f"{prefix}_MODEL_NAME")

        # CONSTITUTIONAL FIX: Fetch secret using a JIT session if detached.
        # This prevents the "Database session has been detached" crash.
        if self._session_factory:
            async with self._session_factory() as session:
                # Create a temporary config service just for this decryption
                jit_config = await ConfigService.create(session)
                api_key = await jit_config.get_secret(
                    f"{prefix}_API_KEY", audit_context=resource.name
                )
        else:
            # Fallback for unconfigured factory (will fail if detached)
            api_key = await self._config.get_secret(f"{prefix}_API_KEY")

        if not api_url or not model_name:
            raise ValueError(f"Missing config for resource '{resource.name}'.")

        if "anthropic" in api_url.lower():
            from shared.infrastructure.llm.providers.anthropic import AnthropicProvider

            return AnthropicProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )

        if "ollama" in api_url.lower() or "11434" in api_url:
            return OllamaProvider(api_url=api_url, model_name=model_name)

        return OpenAIProvider(api_url=api_url, api_key=api_key, model_name=model_name)

    # ID: 9962386f-4b31-5782-ba52-0b2b1655a43e
    async def aget_client_for_role(self, role_name: str, **_: Any) -> LLMClient:
        """Return an LLMClient for the requested cognitive role."""
        self._require_ready()
        assert self._orch is not None
        return await self._orch.get_client_for_role(role_name)

    # ID: 64a09426-e74e-4547-a08f-3af887085bac
    async def get_embedding_for_code(self, source_code: str) -> list[float] | None:
        """Generate an embedding using the Vectorizer role."""
        if not source_code:
            return None
        client = await self.aget_client_for_role("Vectorizer")
        return await client.get_embedding(source_code)

    # ID: 8b9e2ff1-ec8d-4234-b96c-0a2fc1f43804
    async def search_capabilities(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Optional semantic search via Qdrant."""
        if not query:
            return []

        vec = await self.get_embedding_for_code(query)
        if not vec:
            return []

        return await self.qdrant_service.search_similar(vec, limit=limit)
