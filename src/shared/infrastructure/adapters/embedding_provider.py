# src/shared/infrastructure/adapters/embedding_provider.py

"""
Compatibility shim for legacy imports.

CORE embedding contract:
- Embeddings are local-only.
- No provider switching.
- No os.getenv / fallback chains.
- Async-first (httpx).

This module exists only to prevent import breakage while migrating call sites
to `shared.utils.embedding_utils.EmbeddingService`.
"""

from __future__ import annotations

from shared.logger import getLogger
from shared.utils.embedding_utils import (
    Embeddable,
)
from shared.utils.embedding_utils import (
    EmbeddingService as LocalEmbeddingService,
)


logger = getLogger(__name__)


# ID: 0d57f8d8-c519-421a-834a-1179cef120b9
class EmbeddingService(Embeddable):
    """
    Legacy-compatible wrapper around the canonical local-only EmbeddingService.

    Accepts the old constructor signature used by the previous provider-switching client,
    but ignores parameters that violate CORE's contract (api_key, autodetection, etc.).
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        expected_dim: int | None = None,
        request_timeout_sec: float = 120.0,
        connect_timeout_sec: float = 10.0,
        max_retries: int = 4,
    ) -> None:
        # NOTE: model/base_url are intentionally ignored because canonical service reads
        # strict settings from shared.config.settings (CORE contract).
        # api_key is also ignored (local-only).
        _ = (model, base_url, api_key, expected_dim, connect_timeout_sec, max_retries)

        # Map legacy request timeout to canonical httpx timeout.
        self._svc = LocalEmbeddingService(timeout=float(request_timeout_sec))

        logger.warning(
            "Legacy EmbeddingService shim in use. Migrate to shared.utils.embedding_utils.EmbeddingService."
        )

    # ID: fcf70a54-2a10-4ba1-a19e-56fc1c398456
    async def get_embedding(self, text: str) -> list[float]:
        return await self._svc.get_embedding(text)
