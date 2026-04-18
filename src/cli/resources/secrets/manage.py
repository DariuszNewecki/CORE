# src/cli/resources/secrets/manage.py
"""
CLI commands for encrypted secrets management.
Constitutional compliance: agent_governance, data_governance, operations.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import time

import typer
from rich.table import Table

from cli.utils import (
    confirm_action,
    core_command,
    display_error,
    display_info,
    display_success,
    display_warning,
)
from shared.action_types import ActionImpact, ActionResult
from shared.exceptions import SecretNotFoundError, SecretsError
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.secrets_service import get_secrets_service

from .hub import app


AUDIT_CONTEXT_SET = "cli:set"
AUDIT_CONTEXT_SET_CHECK = "cli:set:check"
AUDIT_CONTEXT_GET = "cli:get"
AUDIT_CONTEXT_LIST = "cli:list"
AUDIT_CONTEXT_DELETE = "cli:delete"


async def _set_secret_internal(
    key: str, value: str, description: str | None, force: bool
) -> ActionResult:
    """Store an encrypted secret in the database."""
    start_time = time.time()
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)
        try:
            overwrite_confirmed = False
            if not force:
                try:
                    await secrets_service.get_secret(
                        db, key, audit_context=AUDIT_CONTEXT_SET_CHECK
                    )
                    if not confirm_action(
                        f"Secret '{key}' already exists. Overwrite?",
                        abort_message="Overwrite cancelled",
                    ):
                        return ActionResult(
                            action_id="secrets.set",
                            ok=False,
                            data={"key": key, "action": "cancelled"},
                            duration_sec=time.time() - start_time,
                            impact=ActionImpact.READ_ONLY,
                            warnings=["User cancelled overwrite"],
                        )
                    overwrite_confirmed = True
                except SecretNotFoundError:
                    pass
            await secrets_service.set_secret(
                db,
                key=key,
                value=value,
                description=description,
                audit_context=AUDIT_CONTEXT_SET,
            )
            display_success(f"Secret '{key}' stored successfully")
            return ActionResult(
                action_id="secrets.set",
                ok=True,
                data={
                    "key": key,
                    "action": "overwritten" if overwrite_confirmed else "created",
                    "has_description": description is not None,
                },
                duration_sec=time.time() - start_time,
                impact=ActionImpact.WRITE_DATA,
            )
        except SecretsError as exc:
            display_error(f"Failed to store secret: {exc.message}")
            return ActionResult(
                action_id="secrets.set",
                ok=False,
                data={"key": key, "error": exc.message},
                duration_sec=time.time() - start_time,
                impact=ActionImpact.READ_ONLY,
                warnings=[str(exc)],
            )


async def _get_internal(key: str, show: bool) -> ActionResult:
    """Retrieve and decrypt a secret from the database."""
    start_time = time.time()
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)
        try:
            value = await secrets_service.get_secret(
                db, key, audit_context=AUDIT_CONTEXT_GET
            )
            if show:
                display_info(f"Secret '{key}':")
                logger.info(value)
            else:
                display_success(f"Secret '{key}' exists (use --show to display)")
            return ActionResult(
                action_id="secrets.get",
                ok=True,
                data={"key": key, "exists": True, "displayed": show},
                duration_sec=time.time() - start_time,
                impact=ActionImpact.READ_ONLY,
            )
        except SecretNotFoundError:
            display_error(f"Secret '{key}' not found")
            return ActionResult(
                action_id="secrets.get",
                ok=False,
                data={"key": key, "exists": False},
                duration_sec=time.time() - start_time,
                impact=ActionImpact.READ_ONLY,
                warnings=[f"Secret '{key}' not found"],
            )
        except SecretsError as exc:
            display_error(f"Failed to retrieve secret: {exc.message}")
            return ActionResult(
                action_id="secrets.get",
                ok=False,
                data={"key": key, "error": exc.message},
                duration_sec=time.time() - start_time,
                impact=ActionImpact.READ_ONLY,
                warnings=[str(exc)],
            )


async def _list_secrets_internal() -> ActionResult:
    """List all secret keys (not values) in the database."""
    start_time = time.time()
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)
        try:
            secrets_list = await secrets_service.list_secrets(db)
            if not secrets_list:
                display_warning("No secrets found in database")
                return ActionResult(
                    action_id="secrets.list",
                    ok=True,
                    data={"count": 0, "secrets": []},
                    duration_sec=time.time() - start_time,
                    impact=ActionImpact.READ_ONLY,
                )
            table = Table(title="Encrypted Secrets")
            table.add_column("Key", style="cyan", no_wrap=True)
            table.add_column("Description", style="white")
            table.add_column("Last Updated", style="dim")
            for secret in secrets_list:
                table.add_row(
                    secret["key"],
                    secret.get("description") or "",
                    (
                        str(secret.get("last_updated"))
                        if secret.get("last_updated")
                        else "none"
                    ),
                )
            logger.info(table)
            display_info(f"Total: {len(secrets_list)} secrets")
            return ActionResult(
                action_id="secrets.list",
                ok=True,
                data={
                    "count": len(secrets_list),
                    "secrets": [s["key"] for s in secrets_list],
                },
                duration_sec=time.time() - start_time,
                impact=ActionImpact.READ_ONLY,
            )
        except SecretsError as exc:
            display_error(f"Failed to list secrets: {exc.message}")
            return ActionResult(
                action_id="secrets.list",
                ok=False,
                data={"error": exc.message},
                duration_sec=time.time() - start_time,
                impact=ActionImpact.READ_ONLY,
                warnings=[str(exc)],
            )


async def _delete_internal(key: str) -> ActionResult:
    """Delete a secret from the database."""
    start_time = time.time()
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)
        try:
            await secrets_service.delete_secret(db, key)
            display_success(f"Secret '{key}' deleted")
            return ActionResult(
                action_id="secrets.delete",
                ok=True,
                data={"key": key, "action": "deleted"},
                duration_sec=time.time() - start_time,
                impact=ActionImpact.WRITE_DATA,
            )
        except SecretNotFoundError:
            display_error(f"Secret '{key}' not found")
            return ActionResult(
                action_id="secrets.delete",
                ok=False,
                data={"key": key, "exists": False},
                duration_sec=time.time() - start_time,
                impact=ActionImpact.READ_ONLY,
                warnings=[f"Secret '{key}' not found"],
            )
        except SecretsError as exc:
            display_error(f"Failed to delete secret: {exc.message}")
            return ActionResult(
                action_id="secrets.delete",
                ok=False,
                data={"key": key, "error": exc.message},
                duration_sec=time.time() - start_time,
                impact=ActionImpact.READ_ONLY,
                warnings=[str(exc)],
            )


@app.command("set")
@core_command(dangerous=True, requires_context=False)
# ID: 92bcc7e9-189f-45d0-bc18-21512bcba69f
async def set_secret(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Secret key (e.g., 'anthropic.api_key')"),
    value: str = typer.Option(
        ...,
        "--value",
        "-v",
        prompt=True,
        hide_input=True,
        help="Secret value (will be encrypted)",
    ),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Optional description"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite without confirmation"
    ),
) -> None:
    """Store an encrypted secret in the database."""
    if not key.strip():
        display_error("Secret key cannot be empty")
        raise typer.Exit(code=1)
    result = await _set_secret_internal(
        key=key, value=value, description=description, force=force
    )
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("get")
@core_command(dangerous=False, requires_context=False)
# ID: 01608ce2-3fb8-4f0d-ae1a-abaec72369d7
async def get(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Secret key to retrieve"),
    show: bool = typer.Option(False, "--show", "-s", help="Display the secret value"),
) -> None:
    """Retrieve an encrypted secret from the database."""
    result = await _get_internal(key=key, show=show)
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("list")
@core_command(dangerous=False, requires_context=False)
# ID: cf23ee88-7f5e-47e9-91de-7414ef0c36ed
async def list_secrets(ctx: typer.Context) -> None:
    """List all secret keys in the database (does not show values)."""
    result = await _list_secrets_internal()
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("delete")
@core_command(dangerous=True, requires_context=False)
# ID: cc76acdd-0ef9-4602-86b0-09580546dd05
async def delete(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Secret key to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Delete a secret from the database."""
    if not yes and (
        not confirm_action(
            f"Are you sure you want to delete secret '{key}'?",
            abort_message="Deletion cancelled",
        )
    ):
        return
    result = await _delete_internal(key=key)
    if not result.ok:
        raise typer.Exit(code=1)
