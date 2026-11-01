# src/cli/resources/llm_resources/setup.py
"""
core-admin llm-resources setup / check -- one step to a working model (#1374).

`setup` runs, through the API, everything a fresh install needs before any
model call can work: the cognitive roles (project.cognitive_roles), the
system_config row and the two model rows (setup.llm), and for a remote model
its key in the secret store. It ends with `check`, which calls the
embedding model and the chat model once each.

A key is read from the environment variable named by --api-key-env, never
from the command line, so it does not land in shell history. Giving a key
makes the models `remote`; without one they are `local` (any server you run
yourself, Ollama by default).
"""

from __future__ import annotations

import os

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from .hub import app


console = Console()

DEFAULT_URL = "http://localhost:11434"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_CHAT_MODEL = "qwen2.5-coder:7b"
# A local model's first answer includes loading it into memory.
CHECK_TIMEOUT_SECONDS = 300.0


# ID: 1e7b4d9a-3c6f-4a2e-8b5d-9f2c7a4e1b6d
def render_check(data: dict) -> bool:
    """Print the check result; True when both models answered."""
    for part, label in (("embedding", "Embedding model"), ("chat", "Chat model")):
        info = data.get(part) or {}
        if info.get("ok"):
            detail = (
                f"{info.get('dimensions')} dimensions"
                if part == "embedding"
                else "answered"
            )
            console.print(f"[bold green]✓ {label}[/bold green] {detail}")
        else:
            console.print(
                f"[bold red]✗ {label}[/bold red] {info.get('error', 'no answer')}"
            )
    return bool(data.get("ok"))


@app.command(
    "setup",
    help=(
        "Set up the models CORE uses: roles, settings, an embedding model and a "
        "chat model, then check both."
    ),
)
@core_command(dangerous=True, requires_context=False, requires_brain_services=False)
# ID: 6a3f8c1e-9d4b-4e7a-b2c5-1d8e6a3f9c4b
async def llm_resources_setup(
    ctx: typer.Context,
    url: str = typer.Option(
        DEFAULT_URL, "--url", help="Model server URL (Ollama or OpenAI-compatible)."
    ),
    embedding_url: str | None = typer.Option(
        None,
        "--embedding-url",
        help=(
            "Server for the embedding model when it differs from --url (e.g. a "
            "hosted chat model with local Ollama embeddings)."
        ),
    ),
    embedding_model: str = typer.Option(
        DEFAULT_EMBEDDING_MODEL,
        "--embedding-model",
        help="Model for search; must return 768-dimensional vectors.",
    ),
    chat_model: str = typer.Option(
        DEFAULT_CHAT_MODEL, "--chat-model", help="Model for code and reasoning."
    ),
    api_key_env: str | None = typer.Option(
        None,
        "--api-key-env",
        help="Name of the environment variable holding a remote server's API key.",
    ),
    write: bool = typer.Option(False, "--write", help="Apply the setup."),
) -> None:
    """Set up the models; without --write, show what would change."""
    api_key = None
    if api_key_env:
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            console.print(
                f"[bold red]{api_key_env} is not set or empty.[/bold red] "
                f"Export the API key in it, then run this again."
            )
            raise typer.Exit(1)
    # The key belongs to --url. A separate --embedding-url is a server you run
    # yourself (local, no key).
    locality = "remote" if api_key else "local"
    embedding_locality = "local" if embedding_url else locality
    client = CoreApiClient()

    if write:
        roles = await client.cognitive_roles.project(write=True)
        if not roles.get("ok", True):
            console.print(f"[bold red]Roles:[/bold red] {roles.get('data')}")
            raise typer.Exit(1)
        console.print("[green]✓ Cognitive roles in place[/green]")

    response = await client.llm_resources.setup(
        api_url=url,
        embedding_model=embedding_model,
        chat_model=chat_model,
        locality=locality,
        embedding_api_url=embedding_url or "",
        embedding_locality=embedding_locality,
        write=write,
    )
    data = response.get("data", {})
    if not response.get("ok"):
        console.print(f"[bold red]Setup failed:[/bold red] {data.get('error')}")
        for violation in data.get("violations", []):
            console.print(f"  - {violation}")
        raise typer.Exit(1)

    verb = "Set" if write else "Would set"
    console.print(f"{verb} system settings: {data.get('system_config')}")
    console.print(
        f"{verb} embedding model {embedding_model} "
        f"({embedding_locality}, {embedding_url or url})"
    )
    console.print(f"{verb} chat model {chat_model} ({locality}, {url})")
    if data.get("llm_enabled") is False:
        console.print(
            "[yellow]Models are switched off in system_config (llm_enabled "
            "false); this command does not turn them on.[/yellow]"
        )

    if not write:
        return

    if api_key:
        for prefix in data.get("remote_env_prefixes", []):
            try:
                await client.secrets.set_secret(
                    key=f"{prefix}.api_key", value=api_key, force=True
                )
            except RuntimeError as exc:
                console.print(
                    f"[bold red]Could not store the API key:[/bold red] {exc}. "
                    "A remote model needs CORE_MASTER_KEY in .secrets/core.env "
                    "(install-core.sh creates it); restart the API after adding it."
                )
                raise typer.Exit(1) from exc
        console.print("[green]✓ API key stored encrypted[/green]")

    client.timeout = CHECK_TIMEOUT_SECONDS
    check = await client.llm_resources.check()
    if not render_check(check.get("data", {})):
        console.print(
            "Fix the model named above (for Ollama: `ollama pull <model>`), "
            "then run `core-admin llm-resources check`."
        )
        raise typer.Exit(1)


@app.command("check", help="Call the embedding model and the chat model once each.")
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 3c8e1a6d-4f9b-4b2e-a7d3-6e1c9f4a8b2d
async def llm_resources_check(ctx: typer.Context) -> None:
    """Exit 1 unless both models answer."""
    client = CoreApiClient()
    client.timeout = CHECK_TIMEOUT_SECONDS
    response = await client.llm_resources.check()
    if not render_check(response.get("data", {})):
        raise typer.Exit(1)
