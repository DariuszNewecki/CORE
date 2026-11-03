# src/shared/protocols/cognitive.py

"""
Cognitive Service Protocol - The Reasoning Contract.

Defines the interface for Large Language Model (LLM) interactions.
Allows agents to request reasoning and embeddings without being
coupled to specific provider implementations or database logic.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
# ID: f9cf5915-0c9d-4f7b-8915-6a1ceedf6c6f
class CognitiveProtocol(Protocol):
    """
    Structural interface for the central cognitive facade.
    """

    # ID: 216dfad8-24c9-4861-9349-d7092d1ee76a
    async def aget_client_for_role(self, role_name: str, **kwargs: Any) -> Any:
        """
        Return an LLM client configured for a specific cognitive role.
        """
        ...

    # ID: 9bd4942a-b642-4262-89f8-936a16bcf103
    async def get_embedding_for_code(self, source_code: str) -> list[float] | None:
        """
        Generate a semantic embedding vector for a piece of text.
        """
        ...

    # ID: 7e1a4c9d-5b2f-4d68-93a0-8c6f2b1e7d45
    async def aget_vectorizer_client(self) -> Any:
        """
        Return the Vectorizer role's client; it names the model that served
        its embeddings (``served_model``).
        """
        ...

    # ID: 5d0b7c1e-8a2f-4e63-9b4d-1f7a6c3e2d90
    async def get_embed_model_revision(self) -> str | None:
        """
        The governor-pinned revision of the embedding model
        (``core.system_config.embed_model_revision``), or None when unset.
        """
        ...
