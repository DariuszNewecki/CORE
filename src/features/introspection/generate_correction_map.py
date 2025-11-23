# src/features/introspection/generate_correction_map.py

"""
A utility to generate alias maps from semantic clustering results.
It takes the proposed domain mappings and creates a YAML file that can be used
by the AliasResolver to standardize capability keys.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml
from rich.console import Console

from shared.logger import getLogger

logger = getLogger(__name__)


console = Console()


# ID: ebc34284-fdea-4077-8265-5a69bf74f44f
def generate_maps(
    input_path: Path = typer.Option(
        "reports/proposed_domains.json",
        "--input",
        "-i",
        help="Path to the JSON file with proposed domains from clustering.",
        exists=True,
    ),
    output: Path = typer.Option(
        "reports/aliases.yaml",
        "--output",
        "-o",
        help="Path to save the generated aliases YAML file.",
    ),
):
    """
    Generates an alias map from clustering results to a YAML file.
    """
    console.print(
        f"🗺️  Generating alias map from [bold cyan]{input_path}[/bold cyan]..."
    )
    try:
        proposed_domains = json.loads(input_path.read_text("utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Failed to load or parse input file: {e}")
        raise typer.Exit(code=1)
    alias_map = {"aliases": proposed_domains}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.dump(alias_map, indent=2, sort_keys=True), "utf-8")
    console.print(
        f"✅ Successfully generated alias map with {len(proposed_domains)} entries."
    )
    console.print(f"   -> Saved to: [bold green]{output}[/bold green]")


if __name__ == "__main__":
    typer.run(generate_maps)
