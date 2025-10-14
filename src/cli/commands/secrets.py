# src/cli/commands/secrets.py
"""
CLI commands for encrypted secrets management.

Constitutional Principle: Security by Default
- All secrets encrypted at rest
- Audit trail for all access
- No secrets in logs or stdout by default
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from core.secrets_service import get_secrets_service
from services.database.session_manager import get_session
from shared.cli_utils import (
    async_command,
    confirm_action,
    display_error,
    display_info,
    display_success,
    display_warning,
)
from shared.exceptions import SecretNotFoundError, SecretsError

app = typer.Typer(
    name="secrets",
    help="Manage encrypted secrets in the database",
    no_args_is_help=True,
)


@app.command()
@async_command
async def set(
    key: str = typer.Argument(..., help="Secret key (e.g., 'anthropic.api_key')"),
    value: str = typer.Option(
        ...,
        "--value",
        "-v",
        prompt=True,
        hide_input=True,
        help="Secret value (will be encrypted)",
    ),
    description: str = typer.Option(
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
):
    """
    Store an encrypted secret in the database.

    Examples:
        core-admin secrets set anthropic.api_key --value sk-ant-...
        core-admin secrets set openai.api_key  # Will prompt for value
    """
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)

        try:
            # Check if secret already exists
            try:
                existing = await secrets_service.get_secret(
                    db, key, audit_context="cli:set:check"
                )
                if existing and not force:
                    if not confirm_action(f"Secret '{key}' already exists. Overwrite?"):
                        return
            except SecretNotFoundError:
                pass  # Secret doesn't exist, proceed

            # Store the secret
            await secrets_service.set_secret(
                db,
                key=key,
                value=value,
                description=description,
                audit_context="cli:set",
            )

            display_success(f"Secret '{key}' stored successfully")

        except SecretsError as e:
            display_error(f"Failed to store secret: {e.message}")
            raise typer.Exit(1)


@app.command()
@async_command
async def get(
    key: str = typer.Argument(..., help="Secret key to retrieve"),
    show: bool = typer.Option(
        False,
        "--show",
        "-s",
        help="Display the secret value (otherwise just confirms existence)",
    ),
):
    """
    Retrieve an encrypted secret from the database.

    By default, does not display the value (for security).
    Use --show to display it.

    Examples:
        core-admin secrets get anthropic.api_key --show
        core-admin secrets get openai.api_key  # Just checks if exists
    """
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)

        try:
            value = await secrets_service.get_secret(db, key, audit_context="cli:get")

            if show:
                display_info(f"Secret '{key}':")
                print(value)  # Print directly without Rich formatting
            else:
                display_success(f"Secret '{key}' exists (use --show to display)")

        except SecretNotFoundError:
            display_error(f"Secret '{key}' not found")
            raise typer.Exit(1)
        except SecretsError as e:
            display_error(f"Failed to retrieve secret: {e.message}")
            raise typer.Exit(1)


@app.command()
@async_command
async def list():
    """
    List all secret keys in the database (does not show values).

    Examples:
        core-admin secrets list
    """
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)

        try:
            secrets_list = await secrets_service.list_secrets(db)

            if not secrets_list:
                display_warning("No secrets found in database")
                return

            # Create Rich table
            table = Table(title="Encrypted Secrets")
            table.add_column("Key", style="cyan", no_wrap=True)
            table.add_column("Description", style="white")
            table.add_column("Last Updated", style="dim")

            for secret in secrets_list:
                table.add_row(
                    secret["key"],
                    secret.get("description") or "",
                    (
                        str(secret["last_updated"])
                        if secret.get("last_updated")
                        else "N/A"
                    ),
                )

            from shared.cli_utils import console

            console.print(table)
            display_info(f"Total: {len(secrets_list)} secrets")

        except SecretsError as e:
            display_error(f"Failed to list secrets: {e.message}")
            raise typer.Exit(1)


@app.command()
@async_command
async def delete(
    key: str = typer.Argument(..., help="Secret key to delete"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
):
    """
    Delete a secret from the database.

    Examples:
        core-admin secrets delete old.api_key
        core-admin secrets delete temp.token --yes  # Skip confirmation
    """
    if not yes:
        if not confirm_action(
            f"Are you sure you want to delete secret '{key}'?",
            abort_message="Deletion cancelled",
        ):
            return

    async with get_session() as db:
        secrets_service = await get_secrets_service(db)

        try:
            await secrets_service.delete_secret(db, key)
            display_success(f"Secret '{key}' deleted")

        except SecretNotFoundError:
            display_error(f"Secret '{key}' not found")
            raise typer.Exit(1)
        except SecretsError as e:
            display_error(f"Failed to delete secret: {e.message}")
            raise typer.Exit(1)


@app.command()
@async_command
async def migrate_from_env(
    env_file: Path = typer.Option(
        ".env",
        "--file",
        "-f",
        help="Path to .env file to migrate from",
        exists=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be migrated without doing it",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing secrets",
    ),
):
    """
    Migrate API keys from .env file to encrypted database storage.

    This command:
    1. Reads API keys from .env
    2. Encrypts them
    3. Stores them in core.runtime_settings
    4. Optionally updates .env to reference database

    Examples:
        core-admin secrets migrate-from-env --dry-run
        core-admin secrets migrate-from-env --file .env.prod
        core-admin secrets migrate-from-env --overwrite
    """
    from dotenv import dotenv_values

    # Keys that should be migrated (API keys, passwords, tokens)
    SECRET_PATTERNS = [
        "_api_key",
        "_api_secret",
        "_token",
        "_password",
        "_secret",
        "anthropic_",
        "openai_",
    ]

    try:
        # Load .env file
        env_vars = dotenv_values(env_file)

        # Filter to only secret-like keys
        secrets_to_migrate = {
            key: value
            for key, value in env_vars.items()
            if any(pattern in key.lower() for pattern in SECRET_PATTERNS)
            and value  # Skip empty values
        }

        if not secrets_to_migrate:
            display_warning(f"No secrets found in {env_file}")
            return

        display_info(f"Found {len(secrets_to_migrate)} secrets to migrate:")
        for key in secrets_to_migrate:
            print(f"  - {key}")

        if dry_run:
            display_info("Dry run - no changes made")
            return

        if not confirm_action(
            f"Migrate {len(secrets_to_migrate)} secrets to database?",
            abort_message="Migration cancelled",
        ):
            return

        # Migrate secrets
        async with get_session() as db:
            secrets_service = await get_secrets_service(db)
            migrated = 0
            skipped = 0

            for key, value in secrets_to_migrate.items():
                try:
                    # Check if exists
                    try:
                        existing = await secrets_service.get_secret(
                            db, key, audit_context="cli:migrate:check"
                        )
                        if existing and not overwrite:
                            display_warning(f"Skipping existing secret: {key}")
                            skipped += 1
                            continue
                    except SecretNotFoundError:
                        pass

                    # Migrate
                    await secrets_service.set_secret(
                        db,
                        key=key,
                        value=value,
                        description=f"Migrated from {env_file}",
                        audit_context="cli:migrate",
                    )
                    migrated += 1

                except SecretsError as e:
                    display_error(f"Failed to migrate {key}: {e.message}")

            display_success(f"Migrated {migrated} secrets")
            if skipped:
                display_info(
                    f"Skipped {skipped} existing secrets (use --overwrite to replace)"
                )

    except Exception as e:
        display_error(f"Migration failed: {e}")
        raise typer.Exit(1)


@app.command()
@async_command
async def rotate(
    key: str = typer.Argument(..., help="Secret key to rotate"),
    new_value: str = typer.Option(
        ...,
        "--new-value",
        "-n",
        prompt=True,
        hide_input=True,
        help="New secret value",
    ),
):
    """
    Rotate a secret (update with new value and log rotation).

    Examples:
        core-admin secrets rotate anthropic.api_key
    """
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)

        try:
            # Verify secret exists
            await secrets_service.get_secret(db, key, audit_context="cli:rotate:check")

            # Update with new value
            await secrets_service.set_secret(
                db,
                key=key,
                value=new_value,
                description="Rotated secret",
                audit_context="cli:rotate",
            )

            display_success(f"Secret '{key}' rotated successfully")
            display_warning("Remember to update any services using the old value")

        except SecretNotFoundError:
            display_error(f"Secret '{key}' not found")
            raise typer.Exit(1)
        except SecretsError as e:
            display_error(f"Failed to rotate secret: {e.message}")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
