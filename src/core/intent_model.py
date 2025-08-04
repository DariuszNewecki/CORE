# src/core/intent_model.py

"""
CORE Intent Structure Loader
============================

Provides a normalized interface to the declared domain structure in:
.intent/knowledge/source_structure.yaml

Used to enforce boundaries, access rules, and governance alignment
without hardcoding anything.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional


class IntentModel:
    """
    Loads and provides an queryable interface to the source code structure
    defined in .intent/knowledge/source_structure.yaml.
    """
    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initializes the model by loading the source structure definition.

        Args:
            repo_root (Optional[Path]): The root of the repository. Inferred if not provided.
        """
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]
        self.structure_path = self.repo_root / ".intent" / "knowledge" / "source_structure.yaml"
        self.structure: Dict[str, dict] = self._load_structure()

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
                f"Invalid source_structure.yaml: missing top-level 'structure' key"
            )

        return {entry["domain"]: entry for entry in data["structure"]}

#    def get_domains(self) -> List[str]:
#        """Return all domain names defined in the source structure."""
#        return list(self.structure.keys())

#    def get_path_for_domain(self, domain: str) -> Optional[Path]:
#        """Return the expected path prefix for a given domain."""
#        entry = self.structure.get(domain)
#        if entry:
#            return self.repo_root / entry["path"]
#        return None

#    def get_allowed_types(self, domain: str) -> List[str]:
#        """Return allowed file types for a domain."""
#        entry = self.structure.get(domain)
#        return entry.get("restricted_types") or ["python", "yaml", "json", "md"]

#    def get_default_handler(self, domain: str) -> Optional[str]:
#        """Return the default handler (e.g., LLM agent) for a given domain."""
#        entry = self.structure.get(domain)
#        return entry.get("default_handler")

#    def is_editable(self, domain: str) -> bool:
#        """Return whether a domain is editable (used for governance constraints)."""
#        entry = self.structure.get(domain)
#        return entry.get("editable", False)

    def resolve_domain_for_path(self, file_path: Path) -> Optional[str]:
        """
        Given an absolute or relative path, determine which domain it belongs to.
        Prefers deeper (more specific) paths over shorter ones.
        """
        full_path = file_path.resolve()
        sorted_domains = sorted(
            self.structure.items(),
            key=lambda item: len((self.repo_root / item[1]["path"]).parts),
            reverse=True,
        )
        for domain, entry in sorted_domains:
            domain_root = (self.repo_root / entry["path"]).resolve()
            if domain_root in full_path.parents:
                return domain
        return None

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
