# src/shared/utils/yaml_processor.py

"""

Centralized YAML processor for constitutional compliance, providing consistent
parsing and validation of .intent/ files across all governance checks and tools.

This utility enforces dry_by_design by eliminating duplicate YAML loading logic
and provides constitutional features like:
- Safe loading with error context
- Duplicate key tolerance for diagnostic tools
- Schema validation hooks for future use
- Audit-friendly error reporting

All governance checks (manifest_lint, domain_placement, etc.) use this processor
to ensure consistent behavior and error handling across the constitutional audit
pipeline.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from shared.logger import getLogger

logger = getLogger(__name__)


# ID: a9d1d5fb-f17f-4f08-8c85-fafacff4c937
class YAMLProcessor:
    """Centralized YAML processor for constitutional file operations."""

    def __init__(self, allow_duplicates: bool = False) -> None:
        """Initialize the YAML processor with constitutional configuration.

        Args:
            allow_duplicates: If True, allows duplicate keys for diagnostic tools
                             (default: False for strict constitutional compliance)
        """
        self.allow_duplicates = allow_duplicates
        self.yaml = YAML(typ="safe")
        self.yaml.default_flow_style = False  # Prefer block style
        if allow_duplicates:
            self.yaml.allow_duplicate_keys = True
            logger.debug(
                "YAML processor configured for duplicate key tolerance (diagnostic mode)"
            )
        else:
            logger.debug(
                "YAML processor configured for strict constitutional compliance"
            )

    # ID: b4715b26-2d01-47cb-bf6a-4862d3d67ad2
    def load(self, file_path: Path) -> dict[str, Any] | None:
        """Load and parse a constitutional YAML file with error context.

        This is the single entry point for all YAML loading in governance checks,
        ensuring consistent error handling and logging.

        Args:
            file_path: Path to the .intent/ YAML file (e.g., domain manifests, policies)

        Returns:
            Parsed YAML content as dict, or None if file doesn't exist

        Raises:
            ValueError: If file exists but has invalid YAML structure
            OSError: If file system errors occur during reading
        """
        if not file_path.exists():
            logger.debug("YAML file not found (non-error): %s", file_path)
            return None
        try:
            logger.debug("Loading YAML from: %s", file_path)
            with file_path.open("r", encoding="utf-8") as f:
                content = self.yaml.load(f)
            if content is None:
                logger.warning("YAML file is empty: %s", file_path)
                return {}
            if not isinstance(content, dict):
                raise ValueError(
                    f"YAML root must be a mapping (dict), got {type(content).__name__}: {file_path}"
                )
            logger.debug(
                "Successfully loaded YAML: %s ({len(content)} keys)", file_path
            )
            return content
        except Exception as e:
            logger.error("YAML parsing failed for {file_path}: %s", e)
            raise ValueError(
                f"Failed to parse constitutional YAML {file_path}: {e}"
            ) from e

    # ID: 73394e37-41db-4391-93e8-6ced1a61735f
    def load_strict(self, file_path: Path) -> dict[str, Any]:
        """Load YAML with strict constitutional validation (no duplicate keys).

        Use for policy files and schemas where duplicate keys indicate errors.

        Args:
            file_path: Path to the .intent/ YAML file

        Returns:
            Parsed YAML content as dict

        Raises:
            ValueError: If file doesn't exist, has invalid structure, or contains duplicate keys
        """
        if self.allow_duplicates:
            raise ValueError(
                "Cannot use strict mode with duplicate key tolerance enabled"
            )
        content = self.load(file_path)
        if content is None:
            raise ValueError(f"Required constitutional file missing: {file_path}")
        return content

    # ID: c4e2777b-8eb7-4998-96ae-b58427b52c98
    def dump(self, data: dict[str, Any], file_path: Path) -> None:
        """Write YAML content with constitutional formatting.

        Ensures consistent formatting for .intent/ files, preserving order and
        avoiding unnecessary whitespace.

        Args:
            data: Dict to write as YAML
            file_path: Path to write the YAML file

        Raises:
            OSError: If file system errors occur during writing
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            logger.debug("Dumping YAML to: %s", file_path)
            with file_path.open("w", encoding="utf-8") as f:
                self.yaml.dump(data, f)
            logger.debug("Successfully wrote YAML: %s", file_path)
        except Exception as e:
            logger.error("YAML write failed for {file_path}: %s", e)
            raise OSError(
                f"Failed to write constitutional YAML {file_path}: {e}"
            ) from e

    # ID: 3e29104a-f8b2-456d-a901-78943c15b4a0
    def dump_yaml(self, data: Any) -> str:
        """
        Dump data to a YAML string.

        Used for vectorization and creating text representations of
        structured data.

        Args:
            data: Data to dump

        Returns:
            YAML string
        """
        stream = StringIO()
        self.yaml.dump(data, stream)
        return stream.getvalue()


yaml_processor = YAMLProcessor(allow_duplicates=True)
strict_yaml_processor = YAMLProcessor(allow_duplicates=False)
