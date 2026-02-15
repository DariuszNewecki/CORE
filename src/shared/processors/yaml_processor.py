# src/shared/processors/yaml_processor.py

"""
YAML processor implementing BaseProcessor interface.

Eliminates AST duplication detected by purity.no_ast_duplication rule.
"""

from __future__ import annotations

import json
from typing import Any

import yaml

from shared.processors.base_processor import BaseProcessor


# ID: f9d8e7c6-b5a4-9382-7160-5e4d3c2b1a09
class YAMLProcessor(BaseProcessor):
    """
    Centralized YAML processor for constitutional file operations.

    Implements BaseProcessor template methods using yaml module.
    """

    # ID: 03b8879e-20c9-420e-9a4c-6748732f99a7
    def _serialize(self, data: dict[str, Any], file_handle: Any) -> None:
        """Serialize using yaml.dump() with constitutional formatting."""
        yaml.dump(
            data,
            file_handle,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    # ID: ccde777c-d73f-4530-8b20-68b35a955416
    def _deserialize(self, file_handle: Any) -> dict[str, Any] | None:
        """Deserialize using yaml.safe_load()."""
        return yaml.safe_load(file_handle)

    # ID: 8355f747-02fe-42c2-b9bb-d1a1c326baa6
    def _validate_data(self, data: Any) -> bool:
        """
        Validate YAML-serializable data.

        Checks that data can be safely serialized to YAML.
        """
        try:
            yaml.safe_dump(data)
            return True
        except (yaml.YAMLError, TypeError):
            return False

    # ID: f2a3b4c5-d6e7-8f9a-0b1c-2d3e4f5a6b7c
    def _format_name(self) -> str:
        """Return format name for logging."""
        return "YAML"

    # ID: a3b4c5d6-e7f8-9a0b-1c2d-3e4f5a6b7c8d
    def dump_yaml(self, data: Any) -> str:
        """
        Dump data to a JSON string.

        Used for vectorization and creating text representations of
        structured data.

        Args:
            data: Data to dump

        Returns:
            JSON string

        NOTE: Method name kept as dump_yaml for backward compatibility,
        but returns JSON for consistent vectorization format.
        """
        return json.dumps(data, indent=2, ensure_ascii=False)


# Module-level instances for backward compatibility
yaml_processor = YAMLProcessor(allow_duplicates=True)
strict_yaml_processor = YAMLProcessor(allow_duplicates=False)
