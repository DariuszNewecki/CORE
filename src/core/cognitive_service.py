# src/core/cognitive_service.py
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from services.clients.llm_api_client import BaseLLMClient
from services.database.models import CognitiveRole, LlmResource
from services.database.session_manager import get_session
from services.llm.resource_selector import ResourceSelector
from shared.logger import getLogger

log = getLogger(__name__)


# ID: b58a9a64-f3a8-4385-aede-9a91b75cf327
class CognitiveService:
    """
    Manages LLM client lifecycle and provides clients for specific cognitive roles.
    Delegates resource selection to a dedicated ResourceSelector service.
    """

    def __init__(self, repo_path: Path):
        self._repo_path = Path(repo_path)
        self._loaded: bool = False
        self._clients_by_resource_name: Dict[str, BaseLLMClient] = {}
        self._selected_client_by_role: Dict[str, BaseLLMClient] = {}
        self._resource_selector: Optional[ResourceSelector] = None
        self._init_lock = asyncio.Lock()
        # The QdrantService is now a dependency for search.
        # It's assumed to be provided via CoreContext in a real scenario,
        # but we initialize it here for broader usability.
        self.qdrant_service = __import__(
            "services.clients.qdrant_client"
        ).clients.qdrant_client.QdrantService()

    # ID: 4a3d361d-fc92-4b51-8a4a-622d91c36c04
    async def initialize(self) -> None:
        """Initializes the service by loading data from the DB and creating the selector."""
        async with self._init_lock:
            if self._loaded:
                return

            try:
                log.info("CognitiveService initializing from database...")
                async with get_session() as session:
                    res_result = await session.execute(select(LlmResource))
                    role_result = await session.execute(select(CognitiveRole))

                    resources = []
                    for r in res_result.scalars().all():
                        if isinstance(r.performance_metadata, str):
                            r.performance_metadata = json.loads(r.performance_metadata)
                        if isinstance(r.provided_capabilities, str):
                            r.provided_capabilities = json.loads(
                                r.provided_capabilities
                            )
                        resources.append(r)

                    roles = []
                    for role in role_result.scalars().all():
                        if isinstance(role.required_capabilities, str):
                            role.required_capabilities = json.loads(
                                role.required_capabilities
                            )
                        roles.append(role)

                self._resource_selector = ResourceSelector(resources, roles)
                self._initialize_clients(resources)
                self._loaded = True

            except Exception as e:
                log.warning(
                    f"CognitiveService DB init failed ({e}); services may be limited."
                )
                self._resource_selector = ResourceSelector([], [])

    def _initialize_clients(self, resources: List[LlmResource]):
        """Creates LLM clients for all resources that have valid environment configuration."""
        for r in resources:
            prefix = (r.env_prefix or "").strip().upper()
            if not prefix:
                continue

            api_url = os.getenv(f"{prefix}_API_URL")
            api_key = os.getenv(f"{prefix}_API_KEY")
            model_name = os.getenv(f"{prefix}_MODEL_NAME")

            if not api_url or not model_name:
                log.warning(
                    f"Skipping client for resource '{r.name}'. Missing required env vars with prefix '{prefix}_'."
                )
                continue

            self._clients_by_resource_name[r.name] = BaseLLMClient(
                api_url=api_url, api_key=api_key, model_name=model_name
            )
        log.info(f"Initialized {len(self._clients_by_resource_name)} LLM clients.")

    # ID: 9494786d-4335-4ac3-97cc-4242798171cc
    def get_client_for_role(self, role_name: str) -> BaseLLMClient:
        """
        Synchronously gets the best client for a given role.
        """
        if not self._loaded:
            try:
                if asyncio.get_running_loop().is_running():
                    log.warning(
                        "CognitiveService accessed synchronously from event loop. Initialization may be incomplete."
                    )
                else:
                    raise RuntimeError()
            except RuntimeError:
                asyncio.run(self.initialize())

        if role_name in self._selected_client_by_role:
            return self._selected_client_by_role[role_name]

        if not self._resource_selector:
            raise RuntimeError(
                "ResourceSelector not available. Service may not have initialized correctly."
            )

        selected_resource = self._resource_selector.select_resource_for_role(role_name)
        if not selected_resource:
            raise RuntimeError(f"No compatible resource found for role '{role_name}'")

        client = self._clients_by_resource_name.get(selected_resource.name)
        if not client:
            raise RuntimeError(
                f"Resource '{selected_resource.name}' was selected but has no configured client."
            )

        self._selected_client_by_role[role_name] = client
        return client

    # ID: 4364b032-174d-4799-9797-06f0e01e30d0
    async def aget_client_for_role(self, role_name: str) -> BaseLLMClient:
        """Asynchronously gets the best client for a given role."""
        if not self._loaded:
            await self.initialize()
        return self.get_client_for_role(role_name)

    # ID: 775b9cb7-48fd-4bcd-96fa-758b74191a70
    async def get_embedding_for_code(self, source_code: str) -> list[float] | None:
        """Generate embeddings using the correct, role-based client."""
        if not source_code:
            return None
        try:
            client = await self.aget_client_for_role("Vectorizer")
            return await client.get_embedding(source_code)
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {e}") from e

    # ID: 17bcea8d-726a-482e-aa98-b6a24b43a6a0
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
