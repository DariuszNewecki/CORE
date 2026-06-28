# src/cli/resources/auth.py
"""Governor authentication commands (ADR-132).

Provides login / logout / whoami for the CLI session that backs
CoreApiClient's cookie-based authentication against governor-only routes.
"""

from __future__ import annotations

import typer
from rich.console import Console

from api.cli.client import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.infrastructure.cli_session import clear_session, load_session


app = typer.Typer(
    name="auth",
    help="Governor authentication: login, logout, whoami.",
    no_args_is_help=True,
)
console = Console()


@app.command("login")
@command_meta(
    canonical_name="auth.login",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Authenticate as governor and persist session to ~/.config/core/session.json.",
)
@core_command(dangerous=False, requires_context=False)
# ID: fa64277d-0da9-43e8-8d7f-705613ccbc26
async def login_cmd(
    email: str = typer.Option(
        ..., "--email", "-e", prompt=True, help="Governor email."
    ),
    password: str = typer.Option(
        ...,
        "--password",
        "-p",
        prompt=True,
        hide_input=True,
        help="Governor password.",
    ),
) -> None:
    """Authenticate and save the governor session cookie locally."""
    client = CoreApiClient()
    try:
        await client.auth.login(email, password)
        console.print(
            "[green]Logged in.[/green] Session saved to ~/.config/core/session.json"
        )
    except Exception as exc:
        console.print(f"[red]Login failed:[/red] {exc}")
        raise typer.Exit(1)


@app.command("logout")
@command_meta(
    canonical_name="auth.logout",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Revoke the current governor session.",
)
@core_command(dangerous=False, requires_context=False)
# ID: c07787ff-83a6-428d-af8d-b01d87069163
async def logout_cmd() -> None:
    """Revoke the server-side refresh token and clear the local session file."""
    if not load_session():
        console.print("[yellow]No active session.[/yellow]")
        return
    client = CoreApiClient()
    try:
        await client.auth.logout()
    except Exception:
        clear_session()
    console.print("[green]Logged out.[/green]")


@app.command("change-password")
@command_meta(
    canonical_name="auth.change_password",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Change the governor password using the current session.",
)
@core_command(dangerous=False, requires_context=False)
# ID: a2028733-9820-46a7-980e-9b0d179fa71b
async def change_password_cmd(
    current_password: str = typer.Option(
        ..., "--current", "-c", prompt=True, hide_input=True, help="Current password."
    ),
    new_password: str = typer.Option(
        ...,
        "--new",
        "-n",
        prompt=True,
        hide_input=True,
        help="New password.",
        confirmation_prompt=True,
    ),
) -> None:
    """Change the governor password. Revokes all sessions — you must log in again."""
    if not load_session():
        console.print("[yellow]No active session. Run: core-admin auth login[/yellow]")
        raise typer.Exit(1)
    client = CoreApiClient()
    try:
        result = await client.auth.change_password(current_password, new_password)
        clear_session()
        console.print(f"[green]{result.get('message', 'Password changed.')}[/green]")
        console.print("[dim]Run core-admin auth login to start a new session.[/dim]")
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


@app.command("whoami")
@command_meta(
    canonical_name="auth.whoami",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Print the identity encoded in the current session JWT.",
)
@core_command(dangerous=False, requires_context=False)
# ID: 98eaf458-cc57-4774-b5b6-cabe7934f5e9
async def whoami_cmd() -> None:
    """Show the user identity from the current session token."""
    if not load_session():
        console.print("[yellow]No active session. Run: core-admin auth login[/yellow]")
        raise typer.Exit(1)
    client = CoreApiClient()
    try:
        data = await client.auth.whoami()
        console.print(f"[bold]email:[/bold] {data.get('email')}")
        console.print(f"[bold]role:[/bold]  {data.get('role')}")
        console.print(f"[bold]user_id:[/bold] {data.get('user_id')}")
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
