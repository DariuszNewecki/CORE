# src/features/introspection/generate_correction_map.py

"""
A utility to generate alias maps from semantic clustering results.
It takes the proposed domain mappings and creates a YAML file that can be used
by the AliasResolver to standardize capability keys.

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Enforces IntentGuard and audit logging for alias map generation.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: b43ac4db-6806-4db3-b9f3-0b755178401f
class GenerateCorrectionMapError(RuntimeError):
    """Raised when alias map generation fails."""

    def __init__(self, message: str, *, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


# ID: 58cc1c15-5bd9-401e-9bf2-8b64d1550631
def generate_maps(
    input_path: Path | str = Path("reports/proposed_domains.json"),
    output: Path | str = Path("reports/aliases.yaml"),
) -> None:
    """
    Generates an alias map from clustering results to a YAML file via FileHandler.
    """
    input_path = Path(input_path)
    output_path = Path(output)

    logger.info("Generating alias map from %s...", input_path)
    try:
        # We assume input is readable (read operations are governed differently)
        proposed_domains = json.loads(input_path.read_text("utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error("Failed to load or parse input file: %s", e)
        raise GenerateCorrectionMapError(
            "Failed to load or parse input file.", exit_code=1
        ) from e

    alias_map = {"aliases": proposed_domains}
    content_str = yaml.dump(alias_map, indent=2, sort_keys=True)

    # CONSTITUTIONAL FIX: Use the governed mutation surface
    file_handler = FileHandler(str(settings.REPO_PATH))

    try:
        # Resolve to a repo-relative string for FileHandler
        rel_output = str(
            output_path.resolve().relative_to(settings.REPO_PATH.resolve())
        ).replace("\\", "/")

        # Governed write: checks IntentGuard and logs the event
        file_handler.write_runtime_text(rel_output, content_str)

        logger.info(
            "Successfully generated alias map with %s entries.", len(proposed_domains)
        )
        logger.info("   -> Saved to: %s via FileHandler", rel_output)

    except ValueError:
        logger.error(
            "Security Violation: Attempted to write alias map to ungoverned path: %s",
            output_path,
        )
        raise GenerateCorrectionMapError("Path boundary violation.", exit_code=1)
    except Exception as e:
        logger.error("Failed to persist alias map: %s", e)
        raise GenerateCorrectionMapError(f"Persistence failure: {e}", exit_code=1)


if __name__ == "__main__":
    try:
        generate_maps()
    except GenerateCorrectionMapError as exc:
        raise SystemExit(exc.exit_code) from exc
