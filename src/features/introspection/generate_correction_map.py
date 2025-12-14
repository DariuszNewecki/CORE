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

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 58cc1c15-5bd9-401e-9bf2-8b64d1550631
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
    logger.info("Generating alias map from %s...", input_path)
    try:
        proposed_domains = json.loads(input_path.read_text("utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error("Failed to load or parse input file: %s", e)
        raise typer.Exit(code=1)
    alias_map = {"aliases": proposed_domains}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.dump(alias_map, indent=2, sort_keys=True), "utf-8")
    logger.info(
        "Successfully generated alias map with %s entries.", len(proposed_domains)
    )
    logger.info("   -> Saved to: %s", output)


if __name__ == "__main__":
    typer.run(generate_maps)
