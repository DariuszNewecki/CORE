# src/body/atomic/llm_setup_actions.py
"""
setup.llm -- one step that gives a fresh install a working model (#1374).

A fresh database has no ``core.system_config`` row and no
``core.llm_resources`` rows, and nothing in the docs could create them: the
``.env`` LLM settings were never read. This action writes exactly what a
newcomer needs, in one transaction:

- ``core.system_config``: created when absent (``llm_enabled`` true,
  ``operating_mode`` ``local_only`` for local models, ``hybrid`` for remote
  ones). An existing row is changed only when a remote model needs it to
  leave ``local_only``, and then only to ``hybrid``.
- ``core.llm_resources``: two rows through the same validator as
  ``author.llm_resource`` -- ``setup_embedding`` (``embedding``) for the
  Vectorizer role, and ``setup_chat`` with every other canonical capability,
  so each role the prompts name (Coder, LocalCoder, Planner, Architect, ...)
  finds a model.

Roles are not written here: ``project.cognitive_roles`` creates them, and
the CLI runs it first. Keys are not carried either; a remote model's key goes
to the secret store under ``<env_prefix>.api_key``. ``write=False`` validates
and reports without touching the database.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select

from body.atomic.registry import ActionCategory, register_action
from body.infrastructure.repositories.llm_resource_repository import (
    _MUTABLE_FIELDS,
    validate_llm_resource_definition,
)
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.database.models import LlmResource, SystemConfig
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.capability_taxonomy import (
    CapabilityTaxonomyError,
    load_capability_taxonomy,
)
from shared.logger import getLogger


logger = getLogger(__name__)

ACTION_ID = "setup.llm"
EMBEDDING_RESOURCE = "setup_embedding"
CHAT_RESOURCE = "setup_chat"
EMBEDDING_PREFIX = "setup_embedding"
CHAT_PREFIX = "setup_chat"


# ID: 3b7e1c9d-4f2a-4e8b-9c6d-1a5f7e3b9d2c
def build_setup_definitions(
    *,
    api_url: str,
    embedding_model: str,
    chat_model: str,
    locality: str,
    canonical: frozenset[str],
    embedding_api_url: str = "",
    embedding_locality: str = "",
) -> list[dict[str, Any]]:
    """The two llm_resources rows a working install needs.

    The embedding model may live on its own server (``embedding_api_url``,
    ``embedding_locality``): a hosted chat model often has no 768-dimension
    embedding model, so its embeddings stay local.
    """
    chat_capabilities = sorted(canonical - {"embedding"})
    return [
        {
            "name": EMBEDDING_RESOURCE,
            "env_prefix": EMBEDDING_PREFIX,
            "provided_capabilities": ["embedding"],
            "model_name": embedding_model,
            "api_url": embedding_api_url or api_url,
            "locality": embedding_locality or locality,
            "is_available": True,
        },
        {
            "name": CHAT_RESOURCE,
            "env_prefix": CHAT_PREFIX,
            "provided_capabilities": chat_capabilities,
            "model_name": chat_model,
            "api_url": api_url,
            "locality": locality,
            "is_available": True,
        },
    ]


def _fail(start: float, error: str, **extra: Any) -> ActionResult:
    return ActionResult(
        action_id=ACTION_ID,
        ok=False,
        data={"error": error, **extra},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id=ACTION_ID,
    description="Give a fresh install a working embedding and chat model (#1374)",
    category=ActionCategory.STATE,
    policies=["rules/ai/capability_taxonomy_governance"],
    requires_db=True,
    remediates=[],
)
@atomic_action(
    action_id=ACTION_ID,
    intent="Create the system_config row and the two setup llm_resources rows",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: 8d2f6a1e-5c3b-4a9d-b7e4-2f8c1d6a3e5b
async def action_setup_llm(
    core_context: CoreContext,
    write: bool = False,
    api_url: str = "",
    embedding_model: str = "",
    chat_model: str = "",
    locality: str = "local",
    embedding_api_url: str = "",
    embedding_locality: str = "",
    **kwargs: Any,
) -> ActionResult:
    """Validate (write=False) or apply (write=True) the model setup."""
    start = time.time()
    if not (api_url and embedding_model and chat_model):
        return _fail(start, "api_url, embedding_model and chat_model are required")
    for value in (locality, embedding_locality or locality):
        if value not in ("local", "remote"):
            return _fail(start, f"locality must be local or remote, got {value!r}")

    try:
        canonical = frozenset(load_capability_taxonomy())
    except CapabilityTaxonomyError as exc:
        return _fail(start, str(exc), reason="capability_taxonomy_unreadable")

    definitions = build_setup_definitions(
        api_url=api_url,
        embedding_model=embedding_model,
        chat_model=chat_model,
        locality=locality,
        canonical=canonical,
        embedding_api_url=embedding_api_url,
        embedding_locality=embedding_locality,
    )
    violations = [
        f"{d['name']}: {v}"
        for d in definitions
        for v in validate_llm_resource_definition(d, canonical)
    ]
    if violations:
        return _fail(start, "invalid definition", violations=violations)

    any_remote = any(d["locality"] == "remote" for d in definitions)
    needed_mode = "hybrid" if any_remote else "local_only"
    data: dict[str, Any] = {
        "dry_run": not write,
        "resources": [d["name"] for d in definitions],
        # the rows whose key belongs in the secret store
        "remote_env_prefixes": [
            d["env_prefix"] for d in definitions if d["locality"] == "remote"
        ],
    }
    try:
        async with get_session() as session:
            config = (
                await session.execute(select(SystemConfig).limit(1))
            ).scalar_one_or_none()
            if config is None:
                data["system_config"] = f"created ({needed_mode}, llm enabled)"
                if write:
                    session.add(
                        SystemConfig(operating_mode=needed_mode, llm_enabled=True)
                    )
            elif any_remote and config.operating_mode == "local_only":
                data["system_config"] = "operating_mode local_only -> hybrid"
                if write:
                    config.operating_mode = "hybrid"
            else:
                data["system_config"] = (
                    f"kept ({config.operating_mode}, "
                    f"llm {'enabled' if config.llm_enabled else 'disabled'})"
                )
                data["llm_enabled"] = bool(config.llm_enabled)

            for definition in definitions:
                existing = (
                    await session.execute(
                        select(LlmResource).where(
                            LlmResource.name == definition["name"]
                        )
                    )
                ).scalar_one_or_none()
                if not write:
                    continue
                if existing is None:
                    session.add(
                        LlmResource(
                            name=definition["name"],
                            **{
                                f: definition[f]
                                for f in _MUTABLE_FIELDS
                                if f in definition
                            },
                        )
                    )
                else:
                    for field in _MUTABLE_FIELDS:
                        if field in definition:
                            setattr(existing, field, definition[field])
            if write:
                await session.commit()
    except Exception as exc:
        logger.exception("setup.llm failed")
        return _fail(start, str(exc), error_type=type(exc).__name__)

    return ActionResult(
        action_id=ACTION_ID,
        ok=True,
        data=data,
        duration_sec=time.time() - start,
    )
