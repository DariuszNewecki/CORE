# src/shared/utils/text_cleaner.py

"""Provides functionality for the text_cleaner module."""

from __future__ import annotations

import re


# ID: a957aad3-e091-4ec8-a098-2d849abc2600
def clean_text(
    text: str,
    remove_extra_spaces: bool = True,
    remove_empty_lines: bool = True,
    strip_whitespace: bool = True,
    normalize_case: str | None = None,
) -> str:
    """
    Clean and normalize text by applying various transformations.

    Args:
        text: The input text to clean.
        remove_extra_spaces: If True, collapses multiple spaces/tabs to single space.
        remove_empty_lines: If True, removes lines containing only whitespace.
        strip_whitespace: If True, strips leading/trailing whitespace from each line and the entire result.
        normalize_case: Optional case normalization: 'lower' or 'upper'.

    Returns:
        The cleaned text string.
    """
    if not isinstance(text, str):
        raise TypeError(f"Expected string, got {type(text).__name__}")

    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        # Apply space reduction if requested
        if remove_extra_spaces:
            line = re.sub(r"[ \t]+", " ", line)

        # Strip whitespace from each line if requested
        if strip_whitespace:
            line = line.strip()

        # Skip empty lines if requested
        if remove_empty_lines and not line:
            continue

        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)

    # Apply case normalization if requested
    if normalize_case == "lower":
        result = result.lower()
    elif normalize_case == "upper":
        result = result.upper()
    elif normalize_case is not None and normalize_case not in ("lower", "upper"):
        raise ValueError(
            f"normalize_case must be 'lower', 'upper', or None, got '{normalize_case}'"
        )

    # Final strip if requested
    if strip_whitespace:
        result = result.strip()

    return result
