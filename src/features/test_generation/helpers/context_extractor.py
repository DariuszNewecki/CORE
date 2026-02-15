# src/features/test_generation/helpers/context_extractor.py

"""Context extraction utilities for parsing context packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 3adf4c3c-ac1d-4ce1-a445-57fef36fcaf2
class ContextExtractor:
    """Extracts relevant information from ContextPackage objects."""

    @staticmethod
    # ID: 45aa3458-fb54-43ac-9b47-195656ae7ce9
    def extract_target_code(
        context_packet: dict[str, Any], file_path: str, symbol_name: str
    ) -> str:
        """
        Extract the target symbol's source code from context package.

        Args:
            context_packet: Context package from ContextService
            file_path: Target file path
            symbol_name: Symbol name to extract

        Returns:
            Source code string or empty string if not found
        """
        target_canon = Path(file_path).as_posix().lstrip("./")

        for item in context_packet.get("context", []):
            item_type = item.get("item_type")
            item_name = item.get("name", "")
            item_path_raw = item.get("path", "")

            if item_type in ("code", "symbol") and item_name == symbol_name:
                # Canonicalize item path
                item_canon = Path(item_path_raw).as_posix().lstrip("./")
                if target_canon == item_canon:
                    return item.get("content", "")

        # Fallback: find any code matching the file path if symbol-specific match failed
        for item in context_packet.get("context", []):
            if item.get("item_type") == "code":
                item_canon = Path(item.get("path", "")).as_posix().lstrip("./")
                if target_canon == item_canon:
                    return item.get("content", "")

        return ""

    @staticmethod
    # ID: 53569d70-d3a2-4ab4-8454-4dbff8645dd1
    def extract_dependencies(context_packet: dict[str, Any]) -> list[dict]:
        """
        Extract import dependencies from context package.

        Args:
            context_packet: Context package from ContextService

        Returns:
            List of dependency dicts with 'name' and 'path' keys
        """
        dependencies: list[dict[str, str]] = []
        for item in context_packet.get("context", []):
            if item.get("item_type") == "import":
                dependencies.append(
                    {"name": item.get("name", ""), "path": item.get("path", "")}
                )
        return dependencies

    @staticmethod
    # ID: 068a4b4b-e7ad-434f-9981-92e30671b575
    def extract_similar_symbols(context_packet: dict[str, Any]) -> list[dict]:
        """
        Extract similar symbols (via vector search) from context package.

        Args:
            context_packet: Context package from ContextService

        Returns:
            List of up to 3 most similar symbols with code and summary
        """
        similar: list[dict[str, Any]] = []
        for item in context_packet.get("context", []):
            if item.get("item_type") == "symbol" and item.get("similarity", 0) > 0.7:
                similar.append(
                    {
                        "name": item.get("name", ""),
                        "code": (item.get("content", "") or "")[:500],
                        "summary": item.get("summary", ""),
                    }
                )
        return similar[:3]
