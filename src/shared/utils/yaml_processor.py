# src/shared/utils/yaml_processor.py

"""
Centralized JSON processor for constitutional compliance, providing consistent
parsing and validation of .intent/ files across all governance checks and tools.

This utility enforces dry_by_design by eliminating duplicate JSON loading logic
and provides constitutional features like:
- Safe loading with error context
- Duplicate key tolerance for diagnostic tools
- Schema validation hooks for future use
- Audit-friendly error reporting

All governance checks (manifest_lint, domain_placement, etc.) use this processor
to ensure consistent behavior and error handling across the constitutional audit
pipeline.

NOTE: Despite the module name, this now processes JSON files. The name is kept
for backward compatibility during the YAML -> JSON migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a9d1d5fb-f17f-4f08-8c85-fafacff4c937
class YAMLProcessor:
    """Centralized JSON processor for constitutional file operations."""

    def __init__(self, allow_duplicates: bool = False) -> None:
        """Initialize the JSON processor with constitutional configuration.

        Args:
            allow_duplicates: Ignored for JSON (kept for interface compatibility)
        """
        self.allow_duplicates = allow_duplicates
        if allow_duplicates:
            logger.debug(
                "JSON processor configured for duplicate key tolerance (diagnostic mode)"
            )
        else:
            logger.debug(
                "JSON processor configured for strict constitutional compliance"
            )

    # ID: b4715b26-2d01-47cb-bf6a-4862d3d67ad2
    def load(self, file_path: Path) -> dict[str, Any] | None:
        """Load and parse a constitutional JSON file with error context.

        This is the single entry point for all JSON loading in governance checks,
        ensuring consistent error handling and logging.

        Args:
            file_path: Path to the .intent/ JSON file (e.g., domain manifests, policies)

        Returns:
            Parsed JSON content as dict, or None if file doesn't exist

        Raises:
            ValueError: If file exists but has invalid JSON structure
            OSError: If file system errors occur during reading
        """
        if not file_path.exists():
            logger.debug("JSON file not found (non-error): %s", file_path)
            return None
        try:
            logger.debug("Loading JSON from: %s", file_path)
            with file_path.open("r", encoding="utf-8") as f:
                content = json.load(f)
            if content is None:
                logger.warning("JSON file is empty: %s", file_path)
                return {}
            if not isinstance(content, dict):
                raise ValueError(
                    f"JSON root must be an object (dict), got {type(content).__name__}: {file_path}"
                )
            logger.debug(
                "Successfully loaded JSON: %s (%d keys)", file_path, len(content)
            )
            return content
        except json.JSONDecodeError as e:
            logger.error("JSON parsing failed for %s: %s", file_path, e)
            raise ValueError(
                f"Failed to parse constitutional JSON {file_path}: {e}"
            ) from e
        except Exception as e:
            logger.error("JSON read failed for %s: %s", file_path, e)
            raise ValueError(
                f"Failed to read constitutional JSON {file_path}: {e}"
            ) from e

    # ID: 73394e37-41db-4391-93e8-6ced1a61735f
    def load_strict(self, file_path: Path) -> dict[str, Any]:
        """Load JSON with strict constitutional validation.

        Use for policy files and schemas where validation is required.

        Args:
            file_path: Path to the .intent/ JSON file

        Returns:
            Parsed JSON content as dict

        Raises:
            ValueError: If file doesn't exist or has invalid structure
        """
        content = self.load(file_path)
        if content is None:
            raise ValueError(f"Required constitutional file missing: {file_path}")
        return content

    # ID: c4e2777b-8eb7-4998-96ae-b58427b52c98
    def dump(self, data: dict[str, Any], file_path: Path) -> None:
        """Write JSON content with constitutional formatting.

        Ensures consistent formatting for .intent/ files, preserving order and
        readability.

        Args:
            data: Dict to write as JSON
            file_path: Path to write the JSON file

        Raises:
            OSError: If file system errors occur during writing
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            logger.debug("Dumping JSON to: %s", file_path)
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")  # Add trailing newline
            logger.debug("Successfully wrote JSON: %s", file_path)
        except Exception as e:
            logger.error("JSON write failed for %s: %s", file_path, e)
            raise OSError(
                f"Failed to write constitutional JSON {file_path}: {e}"
            ) from e

    # ID: 3e29104a-f8b2-456d-a901-78943c15b4a0
    def dump_yaml(self, data: Any) -> str:
        """Dump data to a JSON string.

        Used for vectorization and creating text representations of
        structured data.

        Args:
            data: Data to dump

        Returns:
            JSON string

        NOTE: Method name kept as dump_yaml for backward compatibility.
        """
        return json.dumps(data, indent=2, ensure_ascii=False)


yaml_processor = YAMLProcessor(allow_duplicates=True)
strict_yaml_processor = YAMLProcessor(allow_duplicates=False)
