# src/core/cognitive_service.py
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

# --- MODIFIED: Import the new configuration service ---
from services.config_service import config_service
from services.database.models import CognitiveRole, LlmResource
from services.database.session_manager import get_session
from services.llm.client import LLMClient
from services.llm.providers.base import AIProvider
from services.llm.providers.ollama import OllamaProvider
from services.llm.providers.openai import OpenAIProvider
from services.llm.resource_selector import ResourceSelector
from shared.logger import getLogger
from sqlalchemy import select

log = getLogger(__name__)


# ID: ea15f23e-0f28-4339-b195-d67ccbcd66b8
class CognitiveService:
    """
    Manages LLM client lifecycle and provides clients for specific cognitive roles.
    Acts as a factory for creating provider-specific clients.
    """

    def __init__(self, repo_path: Path):
        self._repo_path = Path(repo_path)
        self._loaded: bool = False
        self._clients_by_role: Dict[str, LLMClient] = {}
        self._resource_selector: Optional[ResourceSelector] = None
        self._init_lock = asyncio.Lock()
        self.qdrant_service = __import__(
            "services.clients.qdrant_client"
        ).clients.qdrant_client.QdrantService()

    # ID: aa236a14-a886-4d79-b07c-af37a227eef2
    async def initialize(self) -> None:
        """Initializes the service by loading data from the DB and creating the selector."""
        async with self._init_lock:
            if self._loaded:
                return

            # --- START OF DIAGNOSTIC CODE ---
            print("\n" + "=" * 50)
            print("--- RUNNING DIAGNOSTIC: INSIDE CognitiveService.initialize ---")
            print(f"--- Timestamp: {__import__('datetime').datetime.now()} ---")
            # --- END OF DIAGNOSTIC CODE ---

            try:
                log.info("CognitiveService initializing from database...")
                async with get_session() as session:
                    res_result = await session.execute(select(LlmResource))
                    role_result = await session.execute(select(CognitiveRole))
                    resources = [r for r in res_result.scalars().all()]
                    roles = [r for r in role_result.scalars().all()]

                # --- START OF DIAGNOSTIC CODE ---
                print(
                    "\n[DIAGNOSTIC] The following roles were just read from the database:"
                )
                for r in roles:
                    print(
                        f"  - Role: {r.role}, Assigned Resource: {r.assigned_resource}"
                    )
                print("=" * 50 + "\n")
                # --- END OF DIAGNOSTIC CODE ---

                self._resource_selector = ResourceSelector(resources, roles)
                self._loaded = True

            except Exception as e:
                log.warning(
                    f"CognitiveService DB init failed ({e}); services may be limited."
                )
                self._resource_selector = ResourceSelector([], [])

    # --- MODIFIED: This method is now async to read from the DB-backed config service ---
    async def _create_provider_for_resource(self, resource: LlmResource) -> AIProvider:
        """Factory method to instantiate the correct provider for a resource."""
        prefix = (resource.env_prefix or "").strip().upper()
        if not prefix:
            raise ValueError(f"Resource '{resource.name}' is missing env_prefix.")

        # --- MODIFIED: Read from the new config_service instead of os.getenv ---
        api_url = await config_service.get(f"{prefix}_API_URL")
        api_key = await config_service.get(f"{prefix}_API_KEY")
        model_name = await config_service.get(f"{prefix}_MODEL_NAME")

        if not api_url or not model_name:
            raise ValueError(
                f"Missing required config for resource '{resource.name}' with prefix '{prefix}_'. "
                "Ensure values are in the database via `manage dotenv sync`."
            )

        # Determine which provider to use based on name or URL
        if "ollama" in resource.name or (api_url and "11434" in api_url):
            return OllamaProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )

        # Default to OpenAI-compatible
        return OpenAIProvider(api_url=api_url, model_name=model_name, api_key=api_key)

    # ID: e70894ab-cc70-44e5-8e81-6b2dbcdeb09f
    async def aget_client_for_role(self, role_name: str) -> LLMClient:
        """Asynchronously gets the best client for a given role."""
        if not self._loaded:
            await self.initialize()

        if role_name in self._clients_by_role:
            return self._clients_by_role[role_name]

        if not self._resource_selector:
            raise RuntimeError(
                "ResourceSelector not available. Service may not have initialized correctly."
            )

        selected_resource = self._resource_selector.select_resource_for_role(role_name)
        if not selected_resource:
            raise RuntimeError(f"No compatible resource found for role '{role_name}'")

        try:
            # --- MODIFIED: Add await because _create_provider_for_resource is now async ---
            provider = await self._create_provider_for_resource(selected_resource)
            client = LLMClient(provider)
            self._clients_by_role[role_name] = client
            return client
        except ValueError as e:
            raise RuntimeError(
                f"Failed to create client for role '{role_name}': {e}"
            ) from e

    # ID: 3820dff7-87d7-4c0c-ae29-640d48d51bdb
    async def get_embedding_for_code(self, source_code: str) -> list[float] | None:
        """Generate embeddings using the correct, role-based client."""
        if not source_code:
            return None
        try:
            client = await self.aget_client_for_role("Vectorizer")
            return await client.get_embedding(source_code)
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {e}") from e

    # ID: 4c6cceaf-972c-40e8-ab71-cd80f4baabe3
    async def search_capabilities(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Performs a semantic search for capabilities using the vector database."""
        if not self._loaded:
            await self.initialize()

        log.info(f"Performing semantic search for: '{query}'")
        try:
            query_vector = await self.get_embedding_for_code(query)
            if not query_vector:
                log.warning("Could not generate embedding for search query.")
                return []

            search_results = await self.qdrant_service.search_similar(
                query_vector=query_vector, limit=limit
            )
            return search_results
        except Exception as e:
            log.error(f"Semantic search failed: {e}", exc_info=True)
            return []
