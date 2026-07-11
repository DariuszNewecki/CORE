# src/api/v1/secrets_routes.py

"""Secrets management routes — consumer surface (ADR-146 D2).

Provides CRUD operations for encrypted secrets stored in core.secret_store.
All values are encrypted at rest via Fernet (CORE_MASTER_KEY).

CONSTITUTIONAL:
- No direct database session imports; session acquired through api.dependencies.
- No settings imports; secrets service initialised through shared infrastructure.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, get_secrets_service_dep
from shared.exceptions import SecretNotFoundError, SecretsError
from shared.infrastructure.secrets_service import SecretsService
from shared.logger import getLogger


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/secrets", tags=["Secrets"])


# ID: c22aaf0c-9f69-419f-9018-57d2dde08b96
class SecretSetRequest(BaseModel):
    key: str
    value: str
    description: str | None = None
    force: bool = False


# ID: d8a1531a-1fb1-4b93-bbc8-8f3585f44e0a
class SecretRotateRequest(BaseModel):
    new_value: str


@router.get("", summary="List all secret keys")
# ID: 5494a744-715d-49e9-94fc-ec3d4c574167
async def list_secrets(
    session: AsyncSession = Depends(get_api_session),
    svc: SecretsService = Depends(get_secrets_service_dep),
) -> dict:
    """Return all secret keys with timestamps. Values are never returned."""
    secrets = await svc.list_secrets(session)
    return {"secrets": secrets, "count": len(secrets)}


@router.post("", status_code=201, summary="Set a secret")
# ID: 5177689f-5d51-48c5-9496-57955471baca
async def set_secret(
    body: SecretSetRequest,
    session: AsyncSession = Depends(get_api_session),
    svc: SecretsService = Depends(get_secrets_service_dep),
) -> dict:
    """Create or overwrite an encrypted secret.

    Returns 409 if the key already exists and `force` is false.
    """
    existing = True
    try:
        await svc.get_secret(session, body.key, audit_context="api:set:check")
    except SecretNotFoundError:
        existing = False

    if existing and not body.force:
        raise HTTPException(
            status_code=409,
            detail=f"Secret '{body.key}' already exists. Set force=true to overwrite.",
        )

    try:
        await svc.set_secret(
            session,
            key=body.key,
            value=body.value,
            description=body.description,
            audit_context="api:set",
        )
    except SecretsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "key": body.key,
        "action": "overwritten" if existing else "created",
    }


@router.get("/{key}", summary="Get / check a secret")
# ID: be2e7656-48b9-4dff-9460-c0d1561178e7
async def get_secret(
    key: str,
    show: bool = False,
    session: AsyncSession = Depends(get_api_session),
    svc: SecretsService = Depends(get_secrets_service_dep),
) -> dict:
    """Check whether a secret exists, optionally returning its decrypted value.

    Pass `?show=true` to include the plaintext value in the response.
    Defaults to `show=false` to avoid accidental exposure in logs.
    """
    try:
        value = await svc.get_secret(session, key, audit_context="api:get")
    except SecretNotFoundError:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found.")

    result: dict = {"key": key, "exists": True}
    if show:
        result["value"] = value
    return result


@router.delete("/{key}", summary="Delete a secret")
# ID: a59154fe-481d-41d5-a936-d845c7085b92
async def delete_secret(
    key: str,
    session: AsyncSession = Depends(get_api_session),
    svc: SecretsService = Depends(get_secrets_service_dep),
) -> dict:
    """Permanently delete an encrypted secret."""
    try:
        await svc.delete_secret(session, key)
    except SecretNotFoundError:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found.")
    return {"key": key, "deleted": True}


@router.put("/{key}/rotate", summary="Rotate a secret value")
# ID: ec242740-9acb-41ea-bd55-94fc0e8ab138
async def rotate_secret(
    key: str,
    body: SecretRotateRequest,
    session: AsyncSession = Depends(get_api_session),
    svc: SecretsService = Depends(get_secrets_service_dep),
) -> dict:
    """Replace the value of an existing secret and update last_rotated_at."""
    try:
        await svc.rotate_secret(session, key, body.new_value)
    except SecretNotFoundError:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found.")
    except SecretsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"key": key, "rotated": True}
