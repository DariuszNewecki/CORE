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


# ID: 76a522c7-481a-4026-b4eb-2bd570e8cbfc
class YAMLProcessor(BaseProcessor):
    """
    Centralized YAML processor for constitutional file operations.

    Implements BaseProcessor template methods using yaml module.
    """

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

    # ID: e7dadd40-923a-468a-868f-f78e0269eb25
    def _format_name(self) -> str:
        """Return format name for logging."""
        return "YAML"

    # ID: c7ae9caa-2c9c-4a08-bf55-33b365559178
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
