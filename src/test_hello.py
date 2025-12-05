# src/test_hello.py

"""Provides functionality for the test_hello module."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.logger import getLogger

logger = getLogger(__name__)


# ID: 169b36dd-df6b-4bc8-956a-fb236214a062
def create_test_hello_file(write: bool = False) -> dict[str, Any]:
    """
    Create the main test function file src/test_hello.py with a function returning 'Hello CORE'.

    This function generates a simple test file with a function that returns the string 'Hello CORE'.
    It follows the action pattern with dry-run capability for safety.

    Args:
        write: If True, actually create the file. If False (default), show what would be created
               without making changes (dry-run mode).

    Returns:
        Dictionary containing:
        - 'success': Boolean indicating if operation was/would be successful
        - 'message': Description of what was done or would be done
        - 'file_path': Path to the created/would-be-created file
        - 'content': The content that was/would be written
        - 'dry_run': Boolean indicating if this was a dry run

    Raises:
        OSError: If file creation fails when write=True
        ValueError: If invalid parameters are provided
    """
    # Define the target file path
    target_dir = project_root / "src" / "features" / "self_healing" / "test_generation"
    file_path = target_dir / "test_hello.py"

    # Content to write
    content = '''"""
Test hello module for CORE testing infrastructure.

This module provides a simple test function for automated test generation
and self-healing test infrastructure.
"""

from __future__ import annotations


def hello_core() -> str:
    """
    Return a simple greeting string for CORE testing.

    Returns:
        The string 'Hello CORE' for test verification purposes.

    Example:
        >>> hello_core()
        'Hello CORE'
    """
    return "Hello CORE"


if __name__ == "__main__":
    # Simple demonstration when run directly
    print(hello_core())
'''

    result = {
        "success": False,
        "message": "",
        "file_path": str(file_path),
        "content": content,
        "dry_run": not write,
    }

    try:
        # Check if file already exists
        if file_path.exists():
            result["message"] = f"File already exists at {file_path}"
            result["success"] = True
            return result

        # Dry-run mode: show what would happen
        if not write:
            result["message"] = (
                f"Would create file at {file_path} with {len(content)} characters"
            )
            result["success"] = True
            return result

        # Write mode: actually create the file (atomic operation)
        # Ensure directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Create temporary file first
        temp_file = file_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Atomically rename to target file
        temp_file.rename(file_path)

        # Verify the file was created
        if file_path.exists():
            result["message"] = f"Successfully created file at {file_path}"
            result["success"] = True
            logger.info(f"Created test_hello.py at {file_path}")
        else:
            result["message"] = f"Failed to create file at {file_path}"
            result["success"] = False
            logger.error(f"Failed to create test_hello.py at {file_path}")

    except Exception as e:
        error_msg = f"Error creating test_hello.py: {str(e)}"
        result["message"] = error_msg
        result["success"] = False
        logger.error(error_msg, exc_info=True)

    return result


# Example usage when run directly
if __name__ == "__main__":
    # Demonstrate dry-run mode
    print("=== Dry-run mode (write=False) ===")
    dry_run_result = create_test_hello_file(write=False)
    print(f"Success: {dry_run_result['success']}")
    print(f"Message: {dry_run_result['message']}")
    print(f"File path: {dry_run_result['file_path']}")
    print(f"Dry run: {dry_run_result['dry_run']}")

    print("\n=== Write mode (write=True) ===")
    # Uncomment to actually create the file
    # write_result = create_test_hello_file(write=True)
    # print(f"Success: {write_result['success']}")
    # print(f"Message: {write_result['message']}")
    # print(f"File path: {write_result['file_path']}")
    # print(f"Dry run: {write_result['dry_run']}")

    print(
        "\nNote: Write mode is commented out for safety. Uncomment to actually create the file."
    )
