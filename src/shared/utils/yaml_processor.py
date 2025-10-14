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

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from shared.logger import getLogger

log = getLogger("yaml_processor")


# ID: b824d032-49d4-486b-9182-99a76c78843f
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
        if allow_duplicates:
            self.yaml.allow_duplicate_keys = True
            log.debug(
                "YAML processor configured for duplicate key tolerance (diagnostic mode)"
            )
        else:
            log.debug("YAML processor configured for strict constitutional compliance")

    # ID: 78d97bea-bfa3-49b2-ba62-8e4093d84fb0
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
            log.debug(f"YAML file not found (non-error): {file_path}")
            return None

        try:
            log.debug(f"Loading YAML from: {file_path}")
            with file_path.open("r", encoding="utf-8") as f:
                content = self.yaml.load(f)

            if content is None:
                log.warning(f"YAML file is empty: {file_path}")
                return {}

            if not isinstance(content, dict):
                raise ValueError(
                    f"YAML root must be a mapping (dict), got {type(content).__name__}: {file_path}"
                )

            log.debug(f"Successfully loaded YAML: {file_path} ({len(content)} keys)")
            return content

        except Exception as e:
            log.error(f"YAML parsing failed for {file_path}: {e}")
            raise ValueError(
                f"Failed to parse constitutional YAML {file_path}: {e}"
            ) from e

    # ID: 7e913478-a8e9-4e75-bd12-54f2264487c6
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

    # ID: 91acfb90-7639-41f3-b1cc-064e7d8a0d46
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
            log.debug(f"Dumping YAML to: {file_path}")
            with file_path.open("w", encoding="utf-8") as f:
                self.yaml.dump(data, f)
            log.debug(f"Successfully wrote YAML: {file_path}")
        except Exception as e:
            log.error(f"YAML write failed for {file_path}: {e}")
            raise OSError(
                f"Failed to write constitutional YAML {file_path}: {e}"
            ) from e


# Global instance for convenience (used by all governance checks)
# This follows the constitutional pattern of shared singletons for utilities
yaml_processor = YAMLProcessor(
    allow_duplicates=True
)  # Diagnostic tools need duplicate tolerance

# Strict processor for policy/schema validation
strict_yaml_processor = YAMLProcessor(allow_duplicates=False)
