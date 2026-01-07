# src/shared/infrastructure/vector/adapters/constitutional/doc_key_resolver.py

"""
Document Key Resolver

Computes canonical, stable keys for constitutional documents.
Keys are used for vector storage and deduplication.

Design:
- Pure function: file_path + key_root + intent_root → canonical key
- No filesystem I/O (only path manipulation)
- Deterministic output for same inputs

Key format: {key_root}/{relative_path_no_ext}
Examples:
- rules/architecture/style
- policies/code/code_standards
- constitution/authority
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: compute-doc-key
# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
def compute_doc_key(file_path: Path, *, key_root: str, intent_root: Path) -> str:
    """
    Compute canonical document key based on .intent/ structure.

    The key uniquely identifies a document within its category
    (policies, constitution, standards, rules) and preserves
    hierarchical structure.

    Args:
        file_path: Absolute path to the document file
        key_root: Root directory name (policies, constitution, standards, rules)
        intent_root: Absolute path to .intent/ directory

    Returns:
        Canonical key string (e.g., "rules/architecture/style")

    Examples:
        >>> compute_doc_key(
        ...     Path("/repo/.intent/rules/architecture/style.json"),
        ...     key_root="rules",
        ...     intent_root=Path("/repo/.intent")
        ... )
        'rules/architecture/style'
    """
    # Try standard key_root first
    root_dir = intent_root / key_root
    try:
        rel = file_path.resolve().relative_to(root_dir.resolve())
        rel_no_ext = rel.with_suffix("")
        return f"{key_root}/{rel_no_ext.as_posix()}"
    except ValueError:
        pass

    # Fallback: try all known roots (handles mixed structures)
    # This accommodates transitions between directory layouts
    for alternative_root in ["rules", "policies", "standards", "constitution"]:
        alt_dir = intent_root / alternative_root
        try:
            rel = file_path.resolve().relative_to(alt_dir.resolve())
            rel_no_ext = rel.with_suffix("")
            return f"{alternative_root}/{rel_no_ext.as_posix()}"
        except ValueError:
            continue

    # Final fallback: use stem only (should not happen in healthy repo)
    logger.warning(
        "Could not compute canonical doc_key for %s (key_root=%s), using stem fallback",
        file_path,
        key_root,
    )
    return f"{key_root}/{file_path.stem}"
