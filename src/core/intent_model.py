# src/core/intent_model.py
"""
Loads and provides a queryable interface to the declared domain structure defined in .intent/knowledge/source_structure.yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml


# CAPABILITY: core.intent.load_source_structure
class IntentModel:
    """
    Loads and provides an queryable interface to the source code structure
    defined in .intent/knowledge/source_structure.yaml.
    """

    # CAPABILITY: core.intent_model.initialize
    def __init__(self, repo_root: Optional[Path] = None):
        """Initializes the model by loading the source structure definition from the repository, inferring the root if not provided."""
        """
        Initializes the model by loading the source structure definition.

        Args:
            repo_root (Optional[Path]): The root of the repository. Inferred if not provided.
        """
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]
        self.structure_path = (
            self.repo_root / ".intent" / "knowledge" / "source_structure.yaml"
        )
        self.structure: Dict[str, dict] = self._load_structure()

    """Load the domain structure from .intent/knowledge/source_structure.yaml and return a mapping of domain names to metadata (path, permissions, etc.)."""

    # CAPABILITY: core.intent.load_structure
    def _load_structure(self) -> Dict[str, dict]:
        """
        Load the domain structure from .intent/knowledge/source_structure.yaml.

        Returns:
            Dict[str, dict]: Mapping of domain names to metadata (path, permissions, etc.).
        """
        if not self.structure_path.exists():
            raise FileNotFoundError(f"Missing: {self.structure_path}")

        data = yaml.safe_load(self.structure_path.read_text(encoding="utf-8"))

        if not isinstance(data, dict) or "structure" not in data:
            raise ValueError(
                "Invalid source_structure.yaml: missing top-level 'structure' key"
            )

        return {entry["domain"]: entry for entry in data["structure"]}

    # CAPABILITY: core.intent.resolve_domain
    def resolve_domain_for_path(self, file_path: Path) -> Optional[str]:
        """
        Given an absolute or relative path, determine which domain it belongs to.
        Prefers deeper (more specific) paths over shorter ones.
        """
        # --- THIS IS THE FIX ---
        # Ensure the path is resolved relative to THIS model's root, not the CWD.
        full_path = (self.repo_root / file_path).resolve()

        sorted_domains = sorted(
            self.structure.items(),
            key=lambda item: len((self.repo_root / item[1]["path"]).parts),
            reverse=True,
        )
        for domain, entry in sorted_domains:
            domain_root = (self.repo_root / entry["path"]).resolve()
            # Check if the domain_root is the same as the path or one of its parents.
            if domain_root == full_path or domain_root in full_path.parents:
                return domain
        return None

    # CAPABILITY: governance.domain.permissions_query
    def get_domain_permissions(self, domain: str) -> List[str]:
        """
        Return a list of allowed domains that the given domain can import from.

        Args:
            domain (str): The domain to query.

        Returns:
            List[str]: List of allowed domain names, or empty list if not defined.
        """
        entry = self.structure.get(domain, {})
        allowed = entry.get("allowed_imports", [])
        return allowed if isinstance(allowed, list) else []
