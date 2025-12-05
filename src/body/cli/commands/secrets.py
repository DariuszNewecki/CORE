# src/body/cli/commands/secrets.py
"""
CLI commands for encrypted secrets management.
Constitutional compliance: agent_governance, data_governance, operations.

Refactored to use the Constitutional CLI Framework (@core_command).
Migrated to ActionResult pattern for atomic actions compliance.
"""

from __future__ import annotations

import time

import typer
from rich.table import Table
from services.database.session_manager import get_session
from services.secrets_service import get_secrets_service
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import (
    confirm_action,
    console,
    core_command,
    display_error,
    display_info,
    display_success,
    display_warning,
)
from shared.exceptions import SecretNotFoundError, SecretsError

# Audit context tags for observability / governance
AUDIT_CONTEXT_SET = "cli:set"
AUDIT_CONTEXT_SET_CHECK = "cli:set:check"
AUDIT_CONTEXT_GET = "cli:get"
AUDIT_CONTEXT_LIST = "cli:list"
AUDIT_CONTEXT_DELETE = "cli:delete"

app = typer.Typer(
    name="secrets",
    help="Manage encrypted secrets in the database",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Async implementations (atomic actions)
# ---------------------------------------------------------------------------


@atomic_action(
    action_id="secrets.set",
    intent="Store an encrypted secret in the database",
    impact=ActionImpact.WRITE_DATA,
    policies=["data_governance", "agent_governance"],
    category="secrets",
)
# ID: 53
async def _set_secret_internal(
    key: str,
    value: str,
    description: str | None,
    force: bool,
) -> ActionResult:
    """
    Store an encrypted secret in the database.

    Args:
        key: Secret identifier
        value: Plaintext secret value
        description: Optional description
        force: Skip overwrite confirmation

    Returns:
        ActionResult with operation status
    """
    start_time = time.time()

    async with get_session() as db:
        secrets_service = await get_secrets_service(db)

        try:
            overwrite_confirmed = False

            if not force:
                # Check if the secret already exists
                try:
                    await secrets_service.get_secret(
                        db,
                        key,
                        audit_context=AUDIT_CONTEXT_SET_CHECK,
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
                    # No existing secret → proceed normally
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


@atomic_action(
    action_id="secrets.get",
    intent="Retrieve and decrypt a secret from the database",
    impact=ActionImpact.READ_ONLY,
    policies=["data_governance", "agent_governance"],
    category="secrets",
)
# ID: 103
async def _get_internal(key: str, show: bool) -> ActionResult:
    """
    Retrieve and decrypt a secret from the database.

    Args:
        key: Secret identifier
        show: Whether to display the secret value

    Returns:
        ActionResult with retrieval status
    """
    start_time = time.time()

    async with get_session() as db:
        secrets_service = await get_secrets_service(db)
        try:
            value = await secrets_service.get_secret(
                db,
                key,
                audit_context=AUDIT_CONTEXT_GET,
            )

            if show:
                display_info(f"Secret '{key}':")
                console.print(value)
            else:
                display_success(
                    f"Secret '{key}' exists (use --show to display)",
                )

            return ActionResult(
                action_id="secrets.get",
                ok=True,
                data={
                    "key": key,
                    "exists": True,
                    "displayed": show,
                },
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


@atomic_action(
    action_id="secrets.list",
    intent="List all secret keys in the database",
    impact=ActionImpact.READ_ONLY,
    policies=["data_governance"],
    category="secrets",
)
# ID: 136
async def _list_secrets_internal() -> ActionResult:
    """
    List all secret keys (not values) in the database.

    Returns:
        ActionResult with list of secret keys
    """
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
                        else "N/A"
                    ),
                )

            console.print(table)
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


@atomic_action(
    action_id="secrets.delete",
    intent="Delete a secret from the database",
    impact=ActionImpact.WRITE_DATA,
    policies=["data_governance", "agent_governance"],
    category="secrets",
)
# ID: 177
async def _delete_internal(key: str) -> ActionResult:
    """
    Delete a secret from the database.

    Args:
        key: Secret identifier

    Returns:
        ActionResult with deletion status
    """
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


# ---------------------------------------------------------------------------
# CLI commands (thin wrappers)
# ---------------------------------------------------------------------------


@app.command("set")
@core_command(dangerous=True, requires_context=False)
# ID: f3589402-f99a-45a5-9255-a453cce3a7b0
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
        None,
        "--description",
        "-d",
        help="Optional description of this secret",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing secret without confirmation",
    ),
) -> None:
    """
    Store an encrypted secret in the database.
    """
    if not key.strip():
        display_error("Secret key cannot be empty")
        raise typer.Exit(code=1)

    result = await _set_secret_internal(
        key=key,
        value=value,
        description=description,
        force=force,
    )

    if not result.ok:
        raise typer.Exit(code=1)


@app.command("get")
@core_command(dangerous=False, requires_context=False)
# ID: 717e4862-f0cb-4960-8dfc-4edbda7e1177
async def get(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Secret key to retrieve"),
    show: bool = typer.Option(
        False,
        "--show",
        "-s",
        help="Display the secret value (otherwise just confirms existence)",
    ),
) -> None:
    """
    Retrieve an encrypted secret from the database.
    """
    result = await _get_internal(key=key, show=show)

    if not result.ok:
        raise typer.Exit(code=1)


@app.command("list")
@core_command(dangerous=False, requires_context=False)
# ID: 3a04a91d-2f43-4588-a2e8-535418bb7c8c
async def list_secrets(ctx: typer.Context) -> None:
    """
    List all secret keys in the database (does not show values).
    """
    result = await _list_secrets_internal()

    if not result.ok:
        raise typer.Exit(code=1)


@app.command("delete")
@core_command(dangerous=True, requires_context=False)
# ID: 473daa47-5a87-4d63-95d8-7f4ef238199c
async def delete(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Secret key to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """
    Delete a secret from the database.
    """
    if not yes and not confirm_action(
        f"Are you sure you want to delete secret '{key}'?",
        abort_message="Deletion cancelled",
    ):
        return

    result = await _delete_internal(key=key)

    if not result.ok:
        raise typer.Exit(code=1)
