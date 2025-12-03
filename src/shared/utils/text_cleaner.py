# src/shared/utils/text_cleaner.py
"""
Provides functionality for the text_cleaner module.
Refactored to use shared.utils.common_knowledge for whitespace normalization (SSOT).
"""

from __future__ import annotations

import unicodedata

# Import the Single Source of Truth for whitespace normalization
from shared.utils.common_knowledge import normalize_whitespace as _canonical_normalize


# ID: 95528f75-7e92-4b42-bb95-91c30a87bf4d
def remove_emojis(text: str) -> str:
    """
    Remove all emoji characters from the input text.

    Args:
        text: The input string that may contain emojis

    Returns:
        A string with all emoji characters removed

    Example:
        >>> remove_emojis("Hello 👋 World 🌍")
        'Hello  World '
    """
    if not text:
        return text

    # Remove emojis using Unicode character categories
    # Emojis fall under the 'So' (Symbol, Other) category and specific ranges
    cleaned_text = "".join(
        char
        for char in text
        if not unicodedata.category(char).startswith("So")
        and not (0x1F600 <= ord(char) <= 0x1F64F)  # Emoticons
        and not (
            0x1F300 <= ord(char) <= 0x1F5FF
        )  # Miscellaneous Symbols and Pictographs
        and not (0x1F680 <= ord(char) <= 0x1F6FF)  # Transport and Map Symbols
        and not (0x1F700 <= ord(char) <= 0x1F77F)  # Alchemical Symbols
        and not (0x1F780 <= ord(char) <= 0x1F7FF)  # Geometric Shapes Extended
        and not (0x1F800 <= ord(char) <= 0x1F8FF)  # Supplemental Arrows-C
        and not (
            0x1F900 <= ord(char) <= 0x1F9FF
        )  # Supplemental Symbols and Pictographs
        and not (0x1FA00 <= ord(char) <= 0x1FA6F)  # Chess Symbols
        and not (0x1FA70 <= ord(char) <= 0x1FAFF)  # Symbols and Pictographs Extended-A
        and not (0x2600 <= ord(char) <= 0x26FF)  # Miscellaneous Symbols
        and not (0x2700 <= ord(char) <= 0x27BF)  # Dingbats
        and not (0xFE00 <= ord(char) <= 0xFE0F)  # Variation Selectors
    )

    return cleaned_text


# ID: 6179eab2-0469-4b0e-a762-ea353103ab34
def remove_extra_whitespace(text: str) -> str:
    """
    Remove extra whitespace from the input text.

    DELEGATION NOTE:
    This logic is now centralized in shared.utils.common_knowledge.
    We delegate to that implementation to enforce the DRY principle.
    """
    if not text:
        return text

    return _canonical_normalize(text)


# ID: d58d042a-d3ff-48a0-b724-2023d87778ea
def normalize_text(
    text: str,
    remove_emojis_flag: bool = True,
    remove_extra_whitespace_flag: bool = True,
) -> str:
    """
    Normalize text by removing emojis and/or extra whitespace.

    Args:
        text: The input string to normalize
        remove_emojis_flag: If True, remove emojis from the text
        remove_extra_whitespace_flag: If True, normalize whitespace in the text

    Returns:
        A normalized string
    """
    if not text:
        return text

    normalized_text = text

    if remove_emojis_flag:
        normalized_text = remove_emojis(normalized_text)

    if remove_extra_whitespace_flag:
        normalized_text = remove_extra_whitespace(normalized_text)

    return normalized_text
