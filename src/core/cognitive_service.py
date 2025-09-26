# src/core/cognitive_service.py
"""
Manages the provisioning of configured LLM clients for cognitive roles based on
the project's constitutional architecture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.agents.deduction_agent import DeductionAgent
from services.adapters.embedding_provider import EmbeddingService
from services.clients.llm_api_client import BaseLLMClient
from services.clients.qdrant_client import QdrantService
from shared.config import settings
from shared.logger import getLogger
from shared.utils.embedding_utils import _Adapter, chunk_and_embed

log = getLogger(__name__)


class CognitiveService:
    """Manages the lifecycle and provision of role-based LLM clients."""

    def __init__(self, repo_path: Path | None = None):
        """
        Initializes the service by loading and parsing the cognitive architecture
        from the constitution via the settings object.
        """
        # repo_path is kept for potential future use but is no longer the primary way to find configs
        self.repo_path = repo_path or settings.REPO_PATH
        self._client_cache: Dict[str, BaseLLMClient] = {}
        self._deduction_agent = DeductionAgent()

        # --- THIS IS THE REFACTOR ---
        # The service now loads its governing policies by their logical names.
        self.roles_policy = settings.load(
            "charter.policies.agent.cognitive_roles_policy"
        )
        self._roles_map = {
            role["role"]: role for role in self.roles_policy.get("cognitive_roles", [])
        }

        # The deduction agent now handles loading the resource manifest itself.
        self._resources_map = {
            res["name"]: res
            for res in self._deduction_agent.resource_manifest.get("llm_resources", [])
        }
        # --- END OF REFACTOR ---

        log.info(
            f"CognitiveService initialized with {len(self._roles_map)} roles and "
            f"{len(self._resources_map)} resources."
        )
        self.qdrant_service = QdrantService()

        self.embedding_service = EmbeddingService(
            model=settings.LOCAL_EMBEDDING_MODEL_NAME,
            base_url=settings.LOCAL_EMBEDDING_API_URL,
            api_key=settings.LOCAL_EMBEDDING_API_KEY,
            expected_dim=settings.LOCAL_EMBEDDING_DIM,
        )

    def get_client_for_role(
        self, role_name: str, task_context: Dict[str, Any] | None = None
    ) -> BaseLLMClient:
        """
        Gets a configured LLM client for a specific cognitive role.
        """
        role_config = self._roles_map.get(role_name)
        if not role_config:
            raise ValueError(f"Cognitive role '{role_name}' is not defined.")

        context = task_context or {}
        context["role_config"] = role_config
        resource_name = self._deduction_agent.select_best_resource(context)

        if resource_name in self._client_cache:
            return self._client_cache[resource_name]

        resource_config = self._resources_map.get(resource_name)
        if not resource_config:
            raise ValueError(f"Resource '{resource_name}' is not in the manifest.")

        env_prefix = resource_config.get("env_prefix", "").upper()

        # Pydantic v2+: Use model_extra for dynamic attribute access
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
            f"Dynamically provisioned client for role '{role_name}' "
            f"using resource '{resource_name}' ({model_name})."
        )
        return client

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
            search_results = self.qdrant_service.search_similar(
                query_vector, limit=limit
            )

            return search_results

        except Exception as e:
            log.error(f"❌ Semantic search failed: {e}", exc_info=True)
            return []
