# src/shared/processors/base_processor.py

"""
Base processor for structured data serialization.

Implements Template Method pattern to eliminate duplication between
JSON and YAML processors while maintaining type safety and clean interfaces.

Ref: Constitutional rule purity.no_ast_duplication
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 9c7ebe88-944a-4caf-bef8-257b7d99aec3
class BaseProcessor(ABC):
    """
    Abstract base for structured data processors.

    Eliminates duplication between JSON and YAML processors by providing
    shared logic while delegating serializer-specific operations to subclasses.

    Template Methods (implemented here):
    - dump(): Serialize data to file
    - load_strict(): Load and validate data

    Abstract Methods (subclasses must implement):
    - _serialize(): Format-specific dump logic
    - _deserialize(): Format-specific load logic
    - _validate_data(): Format-specific validation
    """

    def __init__(self, allow_duplicates: bool = False) -> None:
        """
        Initialize processor with configuration.

        Args:
            allow_duplicates: Whether to allow duplicate keys (diagnostic mode)
        """
        self.allow_duplicates = allow_duplicates

    @abstractmethod
    def _serialize(self, data: dict[str, Any], file_handle: Any) -> None:
        """
        Serialize data using format-specific serializer.

        Args:
            data: Python dict to serialize
            file_handle: Open file handle to write to
        """
        pass

    @abstractmethod
    def _deserialize(self, file_handle: Any) -> dict[str, Any] | None:
        """
        Deserialize data using format-specific parser.

        Args:
            file_handle: Open file handle to read from

        Returns:
            Parsed Python dict, or None if empty
        """
        pass

    @abstractmethod
    def _validate_data(self, data: Any) -> bool:
        """
        Perform format-specific validation.

        Args:
            data: Data to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def _format_name(self) -> str:
        """
        Get format name for logging (e.g., "JSON", "YAML").

        Returns:
            Format name string
        """
        pass

    # ID: cf129dd8-8420-44d7-8702-57e6952f772d
    def dump(self, data: dict[str, Any], file_path: Path) -> None:
        """
        Write data to file with constitutional formatting.

        Template method that:
        1. Creates parent directories if needed
        2. Delegates serialization to subclass
        3. Handles errors uniformly
        4. Adds trailing newline

        Args:
            data: Dict to write
            file_path: Path to write the file

        Raises:
            OSError: If file system errors occur during writing
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            logger.debug("Dumping %s to: %s", self._format_name(), file_path)

            with file_path.open("w", encoding="utf-8") as f:
                self._serialize(data, f)
                f.write("\n")  # Add trailing newline for git-friendly files

            logger.debug("Successfully wrote %s: %s", self._format_name(), file_path)

        except Exception as e:
            logger.error(
                "%s write failed for %s: %s", self._format_name(), file_path, e
            )
            raise OSError(
                f"Failed to write constitutional {self._format_name()} {file_path}: {e}"
            ) from e

    # ID: d350d491-4ea7-4f1d-9891-eb6927921d08
    def load(self, file_path: Path) -> dict[str, Any] | None:
        """
        Load and parse a constitutional file with error context.

        This is the single entry point for file loading, ensuring consistent
        error handling and logging.

        Template method that:
        1. Checks file existence
        2. Delegates parsing to subclass
        3. Validates structure
        4. Handles errors uniformly

        Args:
            file_path: Path to the .intent/ file

        Returns:
            Parsed content as dict, or None if file doesn't exist

        Raises:
            ValueError: If file exists but has invalid structure
            OSError: If file system errors occur during reading
        """
        if not file_path.exists():
            logger.debug(
                "%s file not found (non-error): %s", self._format_name(), file_path
            )
            return None

        try:
            logger.debug("Loading %s from: %s", self._format_name(), file_path)

            with file_path.open("r", encoding="utf-8") as f:
                content = self._deserialize(f)

            if content is None:
                logger.warning("%s file is empty: %s", self._format_name(), file_path)
                return {}

            if not isinstance(content, dict):
                raise ValueError(
                    f"{self._format_name()} root must be an object (dict), "
                    f"got {type(content).__name__}: {file_path}"
                )

            logger.debug(
                "Successfully loaded %s: %s (%d keys)",
                self._format_name(),
                file_path,
                len(content),
            )
            return content

        except ValueError:
            # Re-raise ValueError as-is (already has good context)
            raise
        except Exception as e:
            logger.error(
                "%s parsing failed for %s: %s", self._format_name(), file_path, e
            )
            raise ValueError(
                f"Failed to parse constitutional {self._format_name()} {file_path}: {e}"
            ) from e

    # ID: 1dd423e3-261a-4097-ac70-496ae5f1c3b9
    def load_strict(self, file_path: Path) -> dict[str, Any]:
        """
        Load data with strict constitutional validation.

        Use for policy files and schemas where validation is required.

        Args:
            file_path: Path to the .intent/ file

        Returns:
            Parsed content as dict

        Raises:
            ValueError: If file doesn't exist or has invalid structure
        """
        content = self.load(file_path)
        if content is None:
            raise ValueError(f"Required constitutional file missing: {file_path}")
        return content
