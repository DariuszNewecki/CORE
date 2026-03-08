# src/shared/infrastructure/vector/adapters/constitutional/doc_key_resolver.py

"""
Document Key Resolver - Canonical Identity Engine.

CONSTITUTIONAL FIX (V2.3.0):
- Fixed "Stem Fallback" warnings by recognizing META, phases, and workflows as valid roots.
- Ensures unique, collision-resistant IDs in the Qdrant vector database.
- Aligns with the 'Explicitness over Inference' principle.

CONSTITUTIONAL FIX (V2.4.0):
- Removed hardcoded known_roots list.
- Known roots are now derived from META/intent_tree.yaml at runtime.
- Falls back to scanning actual .intent/ subdirectories if intent_tree.yaml is absent.
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7890-abcd-ef1234567890
def _get_known_roots(intent_root: Path) -> list[str]:
    """
    Derive known .intent/ roots from META/intent_tree.yaml.

    This replaces the hardcoded known_roots list. The authoritative source
    is META/intent_tree.yaml — the same file IntentRepository reads.

    Falls back to scanning actual subdirectories of intent_root if
    intent_tree.yaml is not available, so key resolution never breaks
    even during bootstrapping.
    """
    tree_path = intent_root / "META" / "intent_tree.yaml"

    if tree_path.exists():
        try:
            # Local import to avoid circular dependencies at module level
            from shared.processors.yaml_processor import strict_yaml_processor

            data = strict_yaml_processor.load_strict(tree_path)
            required = data.get("required_directories", [])
            optional = data.get("optional_directories", [])
            return list(dict.fromkeys(required + optional))
        except Exception as e:
            logger.warning(
                "Failed to load META/intent_tree.yaml for key resolution: %s — "
                "falling back to directory scan.",
                e,
            )

    # Fallback: scan actual subdirectories
    try:
        return [
            p.name
            for p in sorted(intent_root.iterdir())
            if p.is_dir() and not p.name.startswith(".")
        ]
    except Exception:
        # Last resort — return minimal known set
        return [
            "rules",
            "constitution",
            "META",
            "enforcement",
            "phases",
            "workflows",
            "workers",
        ]


# ID: 0a4b7ca3-5dad-4aea-a3b2-c11e2dfbbb71
def compute_doc_key(file_path: Path, *, key_root: str, intent_root: Path) -> str:
    """
    Compute canonical document key based on .intent/ structure.
    """
    # 1. Resolve absolute paths to ensure reliable comparison
    abs_file = file_path.resolve()
    abs_intent = intent_root.resolve()

    # 2. THE SEARCH HIERARCHY
    # Known roots are read from META/intent_tree.yaml — not hardcoded.
    known_roots = _get_known_roots(abs_intent)

    for candidate_root in known_roots:
        root_dir = abs_intent / candidate_root
        try:
            rel = abs_file.relative_to(root_dir)
            category_prefix = "metadata" if candidate_root == "META" else candidate_root
            return f"{category_prefix}/{rel.with_suffix('').as_posix()}"
        except ValueError:
            continue

    # 3. FINAL FALLBACK (Last Resort)
    # If the file is in .intent/ but not in a known folder, use its path relative to .intent/
    try:
        rel_to_intent = abs_file.relative_to(abs_intent)
        return rel_to_intent.with_suffix("").as_posix()
    except ValueError:
        logger.warning(
            "Identity Resolution Failure: %s is outside .intent/. Using stem fallback.",
            file_path.name,
        )
        return file_path.stem
