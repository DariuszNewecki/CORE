# src/services/storage/file_classifier.py
"""
File classification utilities for the validation pipeline.

This module provides functionality to classify files based on their extensions,
determining the appropriate validation strategy for each file type.
"""

from __future__ import annotations

from pathlib import Path


# ID: efe53dfb-fd71-4cd1-9f4d-1b1718c4f76a
def get_file_classification(file_path: str) -> str:
    """Determines the file type based on its extension.

    Args:
        file_path: Path to the file to classify

    Returns:
        A string representing the file type ('python', 'yaml', 'text', or 'unknown')
    """
    suffix = Path(file_path).suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in [".yaml", ".yml"]:
        return "yaml"
    if suffix in [".md", ".txt", ".json"]:
        return "text"
    return "unknown"
