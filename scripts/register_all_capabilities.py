#!/usr/bin/env python3
# scripts/register_all_capabilities.py
"""
A helper script to automatically register all unassigned capabilities
found in the knowledge graph.
"""

import json
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import track

# --- Configuration ---
REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_GRAPH_PATH = REPO_ROOT / ".intent" / "knowledge" / "knowledge_graph.json"
# --- End Configuration ---

console = Console()


def main():
    """Main execution function."""
    console.print(
        "[bold cyan]🚀 Batch Registering All Unassigned Capabilities...[/bold cyan]"
    )

    if not KNOWLEDGE_GRAPH_PATH.exists():
        console.print(
            f"[bold red]❌ Error: Knowledge graph not found at {KNOWLEDGE_GRAPH_PATH}[/bold red]"
        )
        sys.exit(1)

    with KNOWLEDGE_GRAPH_PATH.open("r", encoding="utf-8") as f:
        graph = json.load(f)

    symbols = graph.get("symbols", {}).values()

    # --- THIS IS THE DEFINITIVE FIX ---
    # The script now uses the same, correct logic as the auditor to identify
    # only the PUBLIC symbols that are unassigned.
    unassigned_symbols = [
        s
        for s in symbols
        if s.get("capability") == "unassigned" and not s.get("name", "").startswith("_")
    ]
    # --- END OF FIX ---

    if not unassigned_symbols:
        console.print(
            "[bold green]✅ Success! No unassigned public capabilities found.[/bold green]"
        )
        sys.exit(0)

    console.print(
        f"   -> Found {len(unassigned_symbols)} unassigned public capabilities to register."
    )
    console.print(
        "[yellow]This will make multiple calls to the LLM and will take some time.[/yellow]"
    )
    if input("Proceed? (y/N): ").lower() != "y":
        console.print("[bold red]Aborted.[/bold red]")
        sys.exit(0)

    success_count = 0
    fail_count = 0

    for symbol in track(unassigned_symbols, description="Registering capabilities..."):
        symbol_key = symbol.get("key")
        if not symbol_key:
            continue

        command = [
            "poetry",
            "run",
            "core-admin",
            "capability",
            "new",
            symbol_key,
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )
            success_count += 1
        except subprocess.CalledProcessError as e:
            console.print(
                f"\n[bold red]❌ Failed to register '{symbol_key}':[/bold red]"
            )
            console.print(e.stderr)
            fail_count += 1

    console.print("\n--- Batch Registration Summary ---")
    console.print(
        f"[bold green]✅ Successfully registered: {success_count}[/bold green]"
    )
    if fail_count > 0:
        console.print(f"[bold red]❌ Failed to register: {fail_count}[/bold red]")

    console.print(
        "\n[bold cyan]🧠 Rebuilding knowledge graph to reflect all changes...[/bold cyan]"
    )
    try:
        subprocess.run(
            ["poetry", "run", "core-admin", "knowledge", "build-graph"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        console.print(
            "[bold green]✅ Knowledge graph successfully updated.[/bold green]"
        )
    except subprocess.CalledProcessError as e:
        console.print("[bold red]❌ Failed to rebuild knowledge graph:[/bold red]")
        console.print(e.stderr)
        sys.exit(1)

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
