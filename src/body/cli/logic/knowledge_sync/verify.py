# src/body/cli/logic/knowledge_sync/verify.py
"""
Verifies the integrity of exported YAML files by checking their digests.
"""

from __future__ import annotations

from rich.console import Console
from shared.config import settings

from .utils import compute_digest, read_yaml

console = Console()
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"


# ID: 19b318e0-903d-4f25-8948-2c2680856ba1
def run_verify() -> bool:
    """Checks digests of exported YAML files to ensure integrity.

    Returns:
        bool: True if all digests are valid, False otherwise.
    """
    if not EXPORT_DIR.exists():
        console.print(
            f"[bold red]Export directory not found: {EXPORT_DIR}. Cannot verify.[/bold red]"
        )
        return False

    console.print("🔐 Verifying digests of exported YAML files...")

    files_to_check = [
        "capabilities.yaml",
        "symbols.yaml",
        "links.yaml",
        "northstar.yaml",
    ]
    all_ok = True

    for filename in files_to_check:
        path = EXPORT_DIR / filename
        if not path.exists():
            console.print(
                f"  - [yellow]SKIP[/yellow]: [cyan]{filename}[/cyan] does not exist."
            )
            continue

        doc = read_yaml(path)
        items = doc.get("items", [])
        expected_digest = doc.get("digest")

        if not expected_digest:
            console.print(
                f"  - [red]FAIL[/red]: [cyan]{filename}[/cyan] is missing a digest."
            )
            all_ok = False
            continue

        actual_digest = compute_digest(items)

        if expected_digest == actual_digest:
            console.print(
                f"  - [green]PASS[/green]: [cyan]{filename}[/cyan] digest is valid."
            )
        else:
            console.print(
                f"  - [red]FAIL[/red]: [cyan]{filename}[/cyan] digest mismatch!"
            )
            all_ok = False

    if all_ok:
        console.print("[bold green]✅ All digests are valid.[/bold green]")
    else:
        console.print(
            "[bold red]❌ One or more digests failed verification.[/bold red]"
        )

    return all_ok
