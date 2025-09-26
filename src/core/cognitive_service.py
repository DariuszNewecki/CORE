# src/core/cognitive_service.py
"""
Manages the provisioning of configured LLM clients for cognitive roles based on
the project's constitutional architecture.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import text

from core.agents.deduction_agent import DeductionAgent
from services.adapters.embedding_provider import EmbeddingService
from services.clients.llm_api_client import BaseLLMClient
from services.clients.qdrant_client import QdrantService
from services.repositories.db.engine import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.utils.embedding_utils import _Adapter, chunk_and_embed

log = getLogger(__name__)


# ID: aa34ec94-6843-45c5-8558-a9dcd34e60f3
class CognitiveService:
    """Manages the lifecycle and provision of role-based LLM clients."""

    def __init__(self, repo_path: Path | None = None):
        """
        Initializes the service. Policies are loaded asynchronously on first use.
        """
        self.repo_path = repo_path or settings.REPO_PATH
        self._client_cache: Dict[str, BaseLLMClient] = {}
        self._deduction_agent = DeductionAgent()

        self._roles_map: Dict[str, Any] | None = None
        self._resources_map: Dict[str, Any] | None = None
        self._lock = asyncio.Lock()

        log.info(
            "CognitiveService initialized. Policies will be loaded from DB on first use."
        )
        self.qdrant_service = QdrantService()

        # --- THIS IS THE FIX ---
        # The api_key is now correctly passed, and it can be None.
        self.embedding_service = EmbeddingService(
            model=settings.LOCAL_EMBEDDING_MODEL_NAME,
            base_url=settings.LOCAL_EMBEDDING_API_URL,
            api_key=settings.LOCAL_EMBEDDING_API_KEY,  # This is now safe
            expected_dim=settings.LOCAL_EMBEDDING_DIM,
        )
        # --- END OF FIX ---

    async def _load_policies_from_db(self):
        """Loads cognitive roles and LLM resources from the database."""
        async with self._lock:
            if self._roles_map is not None and self._resources_map is not None:
                return

            log.info("Loading cognitive policies from database for the first time...")
            async with get_session() as session:
                # Load roles
                roles_result = await session.execute(
                    text("SELECT * FROM core.cognitive_roles")
                )
                self._roles_map = {
                    row._mapping["role"]: dict(row._mapping) for row in roles_result
                }

                # Load resources
                resources_result = await session.execute(
                    text("SELECT * FROM core.llm_resources")
                )
                self._resources_map = {
                    row._mapping["name"]: dict(row._mapping) for row in resources_result
                }

            # The deduction agent now loads its manifest from the DB as well
            await self._deduction_agent._load_resource_manifest_from_db()

            log.info(
                f"Loaded {len(self._roles_map)} roles and {len(self._resources_map)} resources from DB."
            )

    # ID: 62a17551-c92a-43bd-8544-58fc5ab07468
    async def get_client_for_role(
        self, role_name: str, task_context: Dict[str, Any] | None = None
    ) -> BaseLLMClient:
        """
        Gets a configured LLM client for a specific cognitive role.
        """
        await self._load_policies_from_db()

        role_config = self._roles_map.get(role_name)
        if not role_config:
            raise ValueError(f"Cognitive role '{role_name}' is not defined.")

        context = task_context or {}
        context["role_config"] = role_config
        resource_name = await self._deduction_agent.select_best_resource(context)

        if resource_name in self._client_cache:
            return self._client_cache[resource_name]

        resource_config = self._resources_map.get(resource_name)
        if not resource_config:
            raise ValueError(f"Resource '{resource_name}' is not in the manifest.")

        env_prefix = resource_config.get("env_prefix", "").upper()
        model_extra = settings.model_extra or {}
        api_url = getattr(settings, f"{env_prefix}_API_URL", None) or model_extra.get(
            f"{env_prefix}_API_URL"
        )
        api_key = getattr(settings, f"{env_prefix}_API_KEY", None) or model_extra.get(
            f"{env_prefix}_API_KEY"
        )
        model_name = getattr(
            settings, f"{env_prefix}_MODEL_NAME", None
        ) or model_extra.get(f"{env_prefix}_MODEL_NAME")

        if not api_url or not model_name:
            raise ValueError(
                f"Configuration for resource prefix '{env_prefix}' is missing URL or Model Name."
            )

        client = BaseLLMClient(api_url=api_url, model_name=model_name, api_key=api_key)
        self._client_cache[resource_name] = client

        log.info(
            f"Dynamically provisioned client for role '{role_name}' using resource '{resource_name}' ({model_name})."
        )
        return client

    # ID: 482c11b6-9d96-4c1c-b680-fdb00ea7cb0b
    async def get_embedding_for_code(self, source_code: str) -> List[float]:
        """
        Gets a vector embedding for a piece of source code using the 'Vectorizer' role.
        """
        log.debug("Using dedicated EmbeddingService to generate embedding...")
        try:
            adapter = _Adapter(self.embedding_service)
            embedding_vector = await chunk_and_embed(adapter, source_code)
            return embedding_vector.tolist()
        except Exception as e:
            log.error(f"Failed to generate embedding: {e}", exc_info=True)
            raise

    # ID: a0c7430d-93ee-4cd2-9bc3-3dbf399bf848
    async def search_capabilities(
        self, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Performs a semantic search for capabilities based on a natural language query.
        """
        log.info(f"Performing semantic search for query: '{query}'")
        try:
            log.debug("   -> Vectorizing search query...")
            query_vector = await self.get_embedding_for_code(query)

            log.debug("   -> Searching for similar capabilities in Qdrant...")
            search_results = await self.qdrant_service.search_similar(
                query_vector, limit=limit
            )
            # Add the key to the payload for easier access
            for result in search_results:
                if "payload" in result and "symbol" in result["payload"]:
                    result["payload"]["key"] = result["payload"]["symbol"]

            return search_results

        except Exception as e:
            log.error(f"❌ Semantic search failed: {e}", exc_info=True)
            return []
