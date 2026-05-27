# src/shared/infrastructure/llm/client.py

"""
A simplified LLM Client that acts as a facade over a specific AI provider.

NOW USES: Database-backed configuration instead of environment variables.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.config_service import ConfigService, LLMResourceConfig
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger

from .providers.base import AIProvider


logger = getLogger(__name__)

# Default cognitive_role for embedding calls — Vectorizer is an active row
# in core.cognitive_roles so the FK constraint is satisfied.
_DEFAULT_EMBEDDING_ROLE = "Vectorizer"


# ID: 7a329240-1a5e-440b-9c8a-65ad427b5e65
class LLMClient:
    """
    A client that uses a provider strategy to interact with an LLM API.

    UPDATED: Now reads configuration from database instead of environment variables.
    """

    def __init__(self, provider: AIProvider, resource_config: LLMResourceConfig):
        self.provider = provider
        self.resource_config = resource_config
        self.model_name = provider.model_name
        self._semaphore: asyncio.Semaphore | None = None
        self._last_request_time: float = 0.0

    @classmethod
    # ID: b93deaf4-7da3-4c67-a4b1-e2a9ae1afeea
    async def create(
        cls,
        db: AsyncSession,
        provider: AIProvider,
        resource_name: str,
    ) -> LLMClient:
        """
        Factory method to create LLMClient with database configuration.

        Args:
            db: Database session
            provider: Configured AI provider instance
            resource_name: Name of the LLM resource (e.g., "anthropic", "deepseek_chat")

        Returns:
            Configured LLMClient instance

        Usage:
            config = await ConfigService.create(db)
            resource_config = await LLMResourceConfig.for_resource(config, "anthropic")

            provider = AnthropicProvider(
                api_key=await resource_config.get_api_key(),
                model_name=await resource_config.get_model_name(),
            )

            client = await LLMClient.create(db, provider, "anthropic")
        """
        config = await ConfigService.create(db)
        resource_config = await LLMResourceConfig.for_resource(config, resource_name)
        instance = cls(provider, resource_config)
        max_concurrent = await resource_config.get_max_concurrent()
        instance._semaphore = asyncio.Semaphore(max_concurrent)
        logger.info(
            "Initialized LLMClient for %s (model=%s, max_concurrent=%s)",
            resource_name,
            provider.model_name,
            max_concurrent,
        )
        return instance

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting based on database configuration."""
        rate_limit = await self.resource_config.get_rate_limit()
        if rate_limit > 0:
            now = asyncio.get_event_loop().time()
            time_since_last = now - self._last_request_time
            if time_since_last < rate_limit:
                wait_time = rate_limit - time_since_last
                logger.debug("Rate limiting: waiting %ss", wait_time)
                await asyncio.sleep(wait_time)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request_with_retry(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Generic retry logic with concurrency control.

        Enforces:
        - Max concurrent requests (via semaphore, per attempt)
        - Rate limiting (via delay between requests)
        - Exponential backoff on failures (sleep outside the semaphore)
        """
        if not self._semaphore:
            raise RuntimeError(
                "LLMClient not properly initialized - use create() factory method"
            )

        backoff_delays = [1.0, 2.0, 4.0]
        total_attempts = len(backoff_delays) + 1

        for attempt in range(total_attempts):
            async with self._semaphore:
                await self._enforce_rate_limit()
                try:
                    return await method(*args, **kwargs)
                except Exception as e:
                    error_message = (
                        f"Request failed (attempt {attempt + 1}/{total_attempts}): "
                        f"{type(e).__name__} - {e}"
                    )
                    if attempt >= len(backoff_delays):
                        logger.error(
                            "Final attempt failed: %s",
                            error_message,
                            exc_info=True,
                        )
                        raise
                    logger.warning(
                        "%s. Retrying after backoff...",
                        error_message,
                    )
            # ADR-043 D4: backoff sleep happens outside the semaphore so a
            # failing call releases its slot during the retry delay,
            # preventing the slot pool from filling with retrying-failing
            # calls under audit-scale fan-out.
            wait_time = backoff_delays[attempt] + random.uniform(0, 0.5)
            await asyncio.sleep(wait_time)

    # ID: 32e259f1-415f-4f2e-9d49-08071b12ceba
    async def make_request_async(
        self,
        prompt: str,
        user_id: str = "core_system",
        cognitive_role: str | None = None,
        privacy_level: str = "standard",
    ) -> str:
        """Makes a chat completion request using the configured provider with retries."""
        usage_sink: dict[str, int] = {}
        started = time.monotonic()
        try:
            result = await self._request_with_retry(
                self.provider.chat_completion,
                prompt,
                user_id,
                usage_sink=usage_sink,
            )
            await self._log_exchange(
                cognitive_role=cognitive_role,
                usage_sink=usage_sink,
                started=started,
                privacy_level=privacy_level,
            )
            return result
        except Exception:
            await self._log_exchange(
                cognitive_role=cognitive_role,
                usage_sink=usage_sink,
                started=started,
                privacy_level=privacy_level,
            )
            raise

    # ID: 09f65041-e28e-4832-9336-9d7475e45565
    async def make_request_with_system_async(
        self,
        prompt: str,
        system_prompt: str,
        user_id: str = "core_system",
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        cognitive_role: str | None = None,
        privacy_level: str = "standard",
    ) -> str:
        """
        Makes a governed chat completion request with a constitutional system prompt.

        This is the entry point used by PromptModel.invoke(). All PromptModel
        invocations must flow through this method — direct calls to
        make_request_async bypass constitutional system prompts.

        Args:
            prompt: Filled user template (the rendered user.txt content).
            system_prompt: Constitutional system prompt loaded from system.txt.
            user_id: Audit identifier for tracing.
            max_tokens: Token budget for this invocation, sourced from model.yaml.
                When None, falls back to the operational default.
            response_format: Optional provider-agnostic structured-output contract.
                Supported shapes:
                    {"type": "json_object"}
                    {"type": "json_schema", "schema": {...}}
            cognitive_role: Canonical core.cognitive_roles row driving this call.
                Used for the llm_exchange_log row. PromptModel.invoke() passes
                its manifest.role here.
            privacy_level: 'standard' | 'restricted' | 'redacted' — recorded
                on the exchange log row. Defaults to 'standard'.

        Returns:
            Raw string response from the AI provider.
        """
        if max_tokens is None:
            max_tokens = load_operational_config().llm.default_max_tokens
        usage_sink: dict[str, int] = {}
        started = time.monotonic()
        try:
            result = await self._request_with_retry(
                self.provider.chat_completion,
                prompt,
                user_id,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                response_format=response_format,
                usage_sink=usage_sink,
            )
            await self._log_exchange(
                cognitive_role=cognitive_role,
                usage_sink=usage_sink,
                started=started,
                privacy_level=privacy_level,
            )
            return result
        except Exception:
            await self._log_exchange(
                cognitive_role=cognitive_role,
                usage_sink=usage_sink,
                started=started,
                privacy_level=privacy_level,
            )
            raise

    # ID: 7e13b689-e8ae-48ac-819b-44f8d3b97e22
    async def get_embedding(
        self,
        text: str,
        cognitive_role: str | None = None,
        privacy_level: str = "standard",
    ) -> list[float]:
        """Gets an embedding using the configured provider with retries."""
        usage_sink: dict[str, int] = {}
        started = time.monotonic()
        try:
            result = await self._request_with_retry(
                self.provider.get_embedding,
                text,
                usage_sink=usage_sink,
            )
            await self._log_exchange(
                cognitive_role=cognitive_role or _DEFAULT_EMBEDDING_ROLE,
                usage_sink=usage_sink,
                started=started,
                privacy_level=privacy_level,
            )
            return result
        except Exception:
            await self._log_exchange(
                cognitive_role=cognitive_role or _DEFAULT_EMBEDDING_ROLE,
                usage_sink=usage_sink,
                started=started,
                privacy_level=privacy_level,
            )
            raise

    # ID: 5d8f2c91-7a4b-4e63-9c12-3b8e7f6a5d04
    async def get_embeddings_batch(
        self,
        texts: list[str],
        cognitive_role: str | None = None,
        privacy_level: str = "standard",
    ) -> list[list[float]]:
        """Batch-embed a list of texts via the provider's batch entry point.

        Wraps `provider.get_embeddings_batch` with the same retry policy as
        the single-input path. Writes ONE row to `core.llm_exchange_log`
        per batch (not per text); token usage is summed across the batch
        per #461 D2. Per-text token attribution is not preserved.

        Providers without a native batch implementation inherit the
        base-class default that loops single-input calls — correct, just
        not faster. OllamaProvider overrides for the real speedup.
        """
        if not texts:
            return []
        usage_sink: dict[str, int] = {}
        started = time.monotonic()
        try:
            result = await self._request_with_retry(
                self.provider.get_embeddings_batch,
                texts,
                usage_sink=usage_sink,
            )
            await self._log_exchange(
                cognitive_role=cognitive_role or _DEFAULT_EMBEDDING_ROLE,
                usage_sink=usage_sink,
                started=started,
                privacy_level=privacy_level,
            )
            return result
        except Exception:
            await self._log_exchange(
                cognitive_role=cognitive_role or _DEFAULT_EMBEDDING_ROLE,
                usage_sink=usage_sink,
                started=started,
                privacy_level=privacy_level,
            )
            raise

    async def _log_exchange(
        self,
        cognitive_role: str | None,
        usage_sink: dict[str, int],
        started: float,
        privacy_level: str,
    ) -> None:
        """Write one row to core.llm_exchange_log. Fire-and-forget semantics —
        any DB failure is logged and swallowed so the LLM call result is
        never affected. cognitive_role=None skips the write (the row's NOT
        NULL FK to core.cognitive_roles cannot be satisfied without it)."""
        if not cognitive_role:
            return
        duration_ms = int((time.monotonic() - started) * 1000)
        try:
            from shared.infrastructure.database.models.llm_config import (
                LlmExchangeLog,
            )
            from shared.infrastructure.database.session_manager import get_session

            row = LlmExchangeLog(
                resource_name=self.resource_config.resource_name,
                cognitive_role=cognitive_role,
                prompt_tokens=usage_sink.get("prompt_tokens"),
                completion_tokens=usage_sink.get("completion_tokens"),
                duration_ms=duration_ms,
                model_snapshot=self.model_name,
                cost_estimate=None,
                privacy_level=privacy_level,
            )
            async with get_session() as session:
                session.add(row)
                await session.commit()
        except Exception as e:
            logger.warning(
                "llm_exchange_log write failed for role=%s resource=%s: %s",
                cognitive_role,
                self.resource_config.resource_name,
                e,
            )


# ID: f0962c2a-eb02-4ef6-856f-413472d3a699
async def create_llm_client_for_role(
    db: AsyncSession,
    cognitive_role: str,
) -> LLMClient:
    """
    Factory function to create an LLM client for a specific cognitive role.

    This reads the role's assigned LLM resource from the database and
    creates an appropriately configured client.

    Args:
        db: Database session
        cognitive_role: Role name (e.g., "planner", "coder")

    Returns:
        Configured LLMClient instance

    Raises:
        ValueError: If role not found or not assigned to a resource

    Usage:
        client = await create_llm_client_for_role(db, "planner")
        response = await client.make_request_async("Plan this task...")
    """
    from sqlalchemy import text

    # ADR-052 Phase 3: cognitive_roles.assigned_resource was dropped in
    # favour of role_resource_assignments (priority-ordered FK list).
    # This factory uses the primary assignment (priority=1, is_active=true).
    query = text(
        """
        SELECT rra.resource
        FROM core.role_resource_assignments rra
        JOIN core.cognitive_roles cr ON cr.role = rra.role
        WHERE rra.role = :role
          AND rra.is_active = true
          AND cr.is_active = true
        ORDER BY rra.priority
        LIMIT 1
        """
    )
    result = await db.execute(query, {"role": cognitive_role})
    row = result.fetchone()

    if not row or not row[0]:
        raise ValueError(
            f"Cognitive role '{cognitive_role}' not found or not assigned to a resource"
        )

    resource_name = row[0]
    config = await ConfigService.create(db)
    resource_config = await LLMResourceConfig.for_resource(config, resource_name)
    api_url = await resource_config.get_api_url()
    api_key = await resource_config.get_api_key(audit_context=cognitive_role)
    model_name = await resource_config.get_model_name()

    if "anthropic" in api_url:
        from .providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key=api_key, model_name=model_name)
    elif "deepseek" in api_url:
        from .providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
        )
    elif "ollama" in api_url or "11434" in api_url:
        from .providers.ollama import OllamaProvider

        provider = OllamaProvider(api_url=api_url, model_name=model_name)
    else:
        from .providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
        )

    return await LLMClient.create(db, provider, resource_name)
