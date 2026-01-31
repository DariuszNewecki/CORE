# src/shared/infrastructure/vector/adapters/constitutional/doc_key_resolver.py

"""
Document Key Resolver - Canonical Identity Engine.

CONSTITUTIONAL FIX (V2.3.5):
- Fixed "Stem Fallback" warnings by recognizing META, phases, and workflows as valid roots.
- Ensures unique, collision-resistant IDs in the Qdrant vector database.
- Aligns with the 'Explicitness over Inference' principle.
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
    """
    # 1. Resolve absolute paths to ensure reliable comparison
    abs_file = file_path.resolve()
    abs_intent = intent_root.resolve()

    # 2. THE SEARCH HIERARCHY
    # We check if the file belongs to any of our known architectural categories.
    # This list must match the folders shown in 'tree .intent/'
    known_roots = [
        "rules",
        "constitution",
        "phases",
        "workflows",
        "META",
        "enforcement",
    ]

    for candidate_root in known_roots:
        root_dir = abs_intent / candidate_root
        try:
            # Check if the file is actually inside this folder
            rel = abs_file.relative_to(root_dir)

            # Format: category/path/to/file (minus extension)
            # Example: rules/architecture/async_logic
            # Example: metadata/enums
            category_prefix = "metadata" if candidate_root == "META" else candidate_root
            return f"{category_prefix}/{rel.with_suffix('').as_posix()}"
        except ValueError:
            # Not in this root, keep looking
            continue

    # 3. FINAL FALLBACK (Last Resort)
    # If the file is in .intent/ but not in a known folder, use its path relative to .intent/
    try:
        rel_to_intent = abs_file.relative_to(abs_intent)
        return rel_to_intent.with_suffix("").as_posix()
    except ValueError:
        # Emergency fallback: just the name
        logger.warning(
            "Identity Resolution Failure: %s is outside .intent/. Using stem fallback.",
            file_path.name,
        )
        return file_path.stem
