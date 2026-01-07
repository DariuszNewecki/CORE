# src/shared/utils/text_cleaner.py

"""
UNIX-compliant text processing pipeline.
Separates splitting, line-level cleaning, filtering, and case normalization
into discrete, predictable stages. Satisfies the 'one thing well' principle.
"""

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
    Clean and normalize text using an atomic transformation pipeline.

    The pipeline follows a strict sequence:
    1. Split: Convert input into a list of lines.
    2. Transform: Apply line-level cleaning (strip/collapse) independently.
    3. Filter: Remove lines that are now effectively empty.
    4. Re-join: Reconstruct the string.
    5. Finalize: Apply global case and final trim.
    """
    if not isinstance(text, str):
        raise TypeError(f"Expected string, got {type(text).__name__}")

    # STAGE 1: Splitting
    lines = text.splitlines()

    # STAGE 2: Independent Line Transformation
    transformed = []
    for line in lines:
        # Atomic Operation A: Strip (Line-level)
        if strip_whitespace:
            line = line.strip()

        # Atomic Operation B: Collapse internal spaces
        if remove_extra_spaces:
            # We use a simple regex that respects the line's existing boundaries
            line = re.sub(r"[ \t]+", " ", line)

        transformed.append(line)

    # STAGE 3: Filtering
    if remove_empty_lines:
        # A line is empty if it contains nothing or only whitespace
        transformed = [ln for ln in transformed if ln != ""]

    # STAGE 4: Re-assembly
    result = "\n".join(transformed)

    # STAGE 5: Global Transformations
    if normalize_case == "lower":
        result = result.lower()
    elif normalize_case == "upper":
        result = result.upper()
    elif normalize_case is not None and normalize_case not in ("lower", "upper"):
        raise ValueError(
            f"normalize_case must be 'lower', 'upper', or None, got '{normalize_case}'"
        )

    # FINAL STAGE: Global Trim (Guarantees no leading/trailing junk for the whole block)
    if strip_whitespace:
        result = result.strip()

    return result
