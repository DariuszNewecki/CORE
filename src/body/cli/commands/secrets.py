# src/body/cli/commands/secrets.py
"""
CLI commands for encrypted secrets management.
Constitutional compliance: agent_governance, data_governance, operations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import typer
from rich.table import Table

from services.database.session_manager import get_session
from services.secrets_service import get_secrets_service
from shared.cli_utils import (
    confirm_action,
    console,
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
# Async runner / wrapper
# ---------------------------------------------------------------------------


def _run_async(coro: Awaitable[object]) -> object:
    """
    Run an async coroutine safely from a synchronous context.

    - In a plain CLI process (no running loop), delegate to asyncio.run().
    - In a test (no running loop in sync code), same behaviour.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        # In typical pytest sync tests, this branch won't run.
        # Left here for completeness / agent contexts.
        return loop.run_until_complete(coro)


def _safe_cli_run(factory: Callable[[], Awaitable[object]], command_name: str) -> None:
    """
    Run async implementation and map unexpected failures to consistent CLI error.

    Domain-level failures are handled inside the async functions (where we can
    show nice messages). This wrapper catches "unknown" exceptions.
    """
    try:
        _run_async(factory())
    except typer.Exit:
        # Domain code has already decided the exit code.
        raise
    except Exception as exc:  # pragma: no cover - defensive
        display_error(f"Critical failure in 'secrets {command_name}': {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# Sync CLI commands (Typer entrypoints)
# ---------------------------------------------------------------------------


@app.command("set")
# ID: 603636f8-de14-41e2-94ca-2d8b1f53c342
def set_secret(
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

    Constitutional:
    - safe_by_default
    - change_must_be_logged
    """
    if not key.strip():
        display_error("Secret key cannot be empty")
        raise typer.Exit(code=1)

    _safe_cli_run(
        lambda: _set_secret_internal(
            key=key,
            value=value,
            description=description,
            force=force,
        ),
        command_name="set",
    )


@app.command("get")
# ID: 0e52e782-a86e-44c6-8280-648a4c818cee
def get(
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

    Constitutional: data_governance.privacy.masking.
    """
    _safe_cli_run(
        lambda: _get_internal(key=key, show=show),
        command_name="get",
    )


@app.command("list")
# ID: f5806ba8-652d-4e89-9571-4f52f98a9d76
def list_secrets() -> None:
    """
    List all secret keys in the database (does not show values).

    Constitutional: data_governance.privacy.no_pii_or_secrets.
    """
    _safe_cli_run(_list_secrets_internal, command_name="list")


@app.command("delete")
# ID: 353d398f-0937-43de-8d39-2ca6557fb29b
def delete(
    key: str = typer.Argument(..., help="Secret key to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """
    Delete a secret from the database.

    Constitutional: agent.compliance.respect_cli_registry.
    """
    if not yes and not confirm_action(
        f"Are you sure you want to delete secret '{key}'?",
        abort_message="Deletion cancelled",
    ):
        # User cancellation is not an error.
        return

    _safe_cli_run(lambda: _delete_internal(key=key), command_name="delete")


# ---------------------------------------------------------------------------
# Async implementations (domain logic)
# ---------------------------------------------------------------------------


async def _set_secret_internal(
    key: str,
    value: str,
    description: str | None,
    force: bool,
) -> None:
    """
    Async implementation of `secrets set`.
    """
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)

        try:
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
                        # User cancelled overwrite → clean exit (code 0)
                        raise typer.Exit()
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
        except SecretsError as exc:
            display_error(f"Failed to store secret: {exc.message}")
            raise typer.Exit(code=1) from exc


async def _get_internal(key: str, show: bool) -> None:
    """
    Async implementation of `secrets get`.
    """
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
        except SecretNotFoundError:
            display_error(f"Secret '{key}' not found")
            raise typer.Exit(code=1)
        except SecretsError as exc:
            display_error(f"Failed to retrieve secret: {exc.message}")
            raise typer.Exit(code=1) from exc


async def _list_secrets_internal() -> None:
    """
    Async implementation of `secrets list`.
    """
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)
        try:
            secrets_list = await secrets_service.list_secrets(db)
            if not secrets_list:
                display_warning("No secrets found in database")
                return

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
        except SecretsError as exc:
            display_error(f"Failed to list secrets: {exc.message}")
            raise typer.Exit(code=1) from exc


async def _delete_internal(key: str) -> None:
    """
    Async implementation of `secrets delete`.
    """
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)
        try:
            await secrets_service.delete_secret(db, key)
            display_success(f"Secret '{key}' deleted")
        except SecretNotFoundError:
            display_error(f"Secret '{key}' not found")
            raise typer.Exit(code=1)
        except SecretsError as exc:
            display_error(f"Failed to delete secret: {exc.message}")
            raise typer.Exit(code=1) from exc
