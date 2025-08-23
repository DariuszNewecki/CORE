# src/core/cognitive_service.py
"""
The CognitiveService is the central nervous system for CORE's reasoning capabilities.
It reads the Mind's intent regarding cognitive roles and resources, and provides
configured LLM clients to the Body's agents. This service leverages the centralized
Pydantic Settings for configuration.
"""
from pathlib import Path
from typing import Dict

from core.clients import BaseLLMClient
from shared.config import settings
from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)


class CognitiveService:
    """Manages the lifecycle and provision of role-based LLM clients."""

    def __init__(self, repo_path: Path):
        """
        Initializes the service by loading and parsing the cognitive architecture from the constitution.
        """
        self.repo_path = repo_path
        self._client_cache: Dict[str, BaseLLMClient] = {}

        # Load the constitution
        self.roles_policy = load_config(
            repo_path / ".intent/knowledge/cognitive_roles.yaml"
        )
        self.resource_manifest = load_config(
            repo_path / ".intent/knowledge/resource_manifest.yaml"
        )

        # Pre-process for efficient lookups
        self._roles_map = {
            role["role"]: role for role in self.roles_policy.get("cognitive_roles", [])
        }
        self._resources_map = {
            res["name"]: res for res in self.resource_manifest.get("llm_resources", [])
        }

        log.info(
            f"CognitiveService initialized with {len(self._roles_map)} roles and {len(self._resources_map)} resources."
        )

    def get_client_for_role(self, role_name: str) -> BaseLLMClient:
        """
        Gets a configured LLM client for a specific cognitive role using the central settings object.
        """
        if role_name in self._client_cache:
            return self._client_cache[role_name]

        role_config = self._roles_map.get(role_name)
        if not role_config:
            raise ValueError(
                f"Cognitive role '{role_name}' is not defined in the constitution."
            )

        resource_name = role_config.get("assigned_resource")
        resource_config = self._resources_map.get(resource_name)
        if not resource_config:
            raise ValueError(
                f"Resource '{resource_name}' for role '{role_name}' is not in the manifest."
            )

        env_prefix = resource_config.get("env_prefix", "").upper()

        # Read from the validated Pydantic settings object, not os.getenv
        api_url = getattr(settings, f"{env_prefix}_API_URL", None)
        api_key = getattr(settings, f"{env_prefix}_API_KEY", None)
        model_name = getattr(settings, f"{env_prefix}_MODEL_NAME", None)

        if not all([api_url, api_key, model_name]):
            raise ValueError(
                f"Configuration for resource prefix '{env_prefix}' is missing in the environment."
            )

        client = BaseLLMClient(api_url=api_url, api_key=api_key, model_name=model_name)
        self._client_cache[role_name] = client

        log.info(
            f"Instantiated LLM client for role '{role_name}' using resource '{resource_name}' ({model_name})."
        )
        return client
