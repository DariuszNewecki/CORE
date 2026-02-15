# src/shared/processors/json_processor.py

"""
JSON processor implementing BaseProcessor interface.

Eliminates AST duplication detected by purity.no_ast_duplication rule.
"""

from __future__ import annotations

import json
from typing import Any

from shared.processors.base_processor import BaseProcessor


# ID: cb19f31b-806a-4e8e-a340-4061259c72bf
class JSONProcessor(BaseProcessor):
    """
    Centralized JSON processor for constitutional file operations.

    Implements BaseProcessor template methods using json module.
    """

    # ID: f0b5ecc8-342b-4bc2-b071-cc72bd697bd0
    def _serialize(self, data: dict[str, Any], file_handle: Any) -> None:
        """Serialize using json.dump() with constitutional formatting."""
        json.dump(
            data,
            file_handle,
            indent=2,
            ensure_ascii=False,
        )

    # ID: 953f9ebf-6af1-4f92-9d13-a4e720a4b36a
    def _deserialize(self, file_handle: Any) -> dict[str, Any] | None:
        """Deserialize using json.load()."""
        return json.load(file_handle)

    # ID: bcdddb18-78d9-4ce2-931a-7dda1699699d
    def _validate_data(self, data: Any) -> bool:
        """
        Validate JSON-serializable data.

        Checks that data contains only JSON-compatible types:
        dict, list, str, int, float, bool, None
        """
        try:
            json.dumps(data)
            return True
        except (TypeError, ValueError):
            return False

    # ID: f9e8984e-6908-4837-81dc-af136030b01e
    def _format_name(self) -> str:
        """Return format name for logging."""
        return "JSON"

    # ID: 3e29104a-f8b2-456d-a901-78943c15b4a0
    def dump_json(self, data: Any) -> str:
        """
        Dump data to a JSON string.

        Used for vectorization and creating text representations of
        structured data.

        Args:
            data: Data to dump

        Returns:
            JSON string
        """
        return json.dumps(data, indent=2, ensure_ascii=False)


# Module-level instances for backward compatibility
json_processor = JSONProcessor(allow_duplicates=True)
strict_json_processor = JSONProcessor(allow_duplicates=False)
