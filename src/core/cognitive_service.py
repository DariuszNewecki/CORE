# src/core/cognitive_service.py
"""
Manages the provisioning of configured LLM clients for cognitive roles based on the project's constitutional architecture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from agents.deduction_agent import DeductionAgent
from core.clients import BaseLLMClient
from shared.config import settings
from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: llm_orchestration.client_provisioning
class CognitiveService:
    """Manages the lifecycle and provision of role-based LLM clients."""

    # CAPABILITY: core.cognitive_service.initialize
    def __init__(self, repo_path: Path):
        """
        Initializes the service by loading and parsing the cognitive architecture from the constitution.
        """
        self.repo_path = repo_path
        self._client_cache: Dict[str, BaseLLMClient] = {}
        # The service now owns the creation of the agent and passes it the config it needs
        self._deduction_agent = DeductionAgent(settings=settings)

        self.roles_policy = load_config(
            repo_path / ".intent/knowledge/cognitive_roles.yaml"
        )
        self._roles_map = {
            role["role"]: role for role in self.roles_policy.get("cognitive_roles", [])
        }
        self._resources_map = {
            res["name"]: res
            for res in self._deduction_agent.resource_manifest.get("llm_resources", [])
        }

        log.info(
            f"CognitiveService initialized with {len(self._roles_map)} roles and {len(self._resources_map)} resources."
        )

    # CAPABILITY: llm_orchestration.client_provisioning
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

        # Access the dynamic variables through `model_extra`
        api_url = settings.model_extra.get(f"{env_prefix}_API_URL")
        api_key = settings.model_extra.get(f"{env_prefix}_API_KEY")
        model_name = settings.model_extra.get(f"{env_prefix}_MODEL_NAME")

        if not all([api_url, api_key, model_name]):
            raise ValueError(
                f"Configuration for resource prefix '{env_prefix}' is missing."
            )

        client = BaseLLMClient(api_url=api_url, api_key=api_key, model_name=model_name)
        self._client_cache[resource_name] = client

        log.info(
            f"Dynamically provisioned client for role '{role_name}' using resource '{resource_name}' ({model_name})."
        )
        return client
