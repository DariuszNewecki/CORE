# src/shared/utils/alias_resolver.py

"""
Provides a utility for loading and resolving capability aliases from the
constitutionally-defined alias map.

If the alias file is missing or unreadable, this resolver degrades gracefully:
- it logs at DEBUG (not WARNING/ERROR), and
- it returns the identity (no aliasing).
"""

from __future__ import annotations

from pathlib import Path

from shared.config import settings
from shared.config_loader import load_yaml_file
from shared.logger import getLogger

logger = getLogger(__name__)
__all__ = ["AliasResolver"]


# ID: b480362b-0395-47e2-87e4-7caa060aa3d6
class AliasResolver:
    """Loads and resolves capability aliases."""

    def __init__(self, alias_file_path: Path | None = None):
        """
        Initializes the resolver by loading the alias map from the constitution.
        Defaults to reports/aliases.yaml.
        """
        self.alias_map: dict[str, str] = {}
        path = alias_file_path or settings.REPO_PATH / "reports" / "aliases.yaml"
        if path.exists():
            try:
                data = load_yaml_file(path)
                self.alias_map = (
                    data.get("aliases", {}) if isinstance(data, dict) else {}
                )
                logger.info(
                    "Loaded %d capability aliases from %s.", len(self.alias_map), path
                )
            except Exception as e:
                self.alias_map = {}
                logger.debug(
                    "Failed to load alias map from %s (%s). Proceeding without aliases.",
                    path,
                    e,
                )
        else:
            self.alias_map = {}
            logger.debug("Alias map not found at %s; proceeding without aliases.", path)

    # ID: aad3c1a9-dcac-4abc-9c06-4d9404df5fe1
    def resolve(self, key: str) -> str:
        """
        Resolves a capability key to its canonical name using the alias map.
        If the key is not an alias, it returns the original key.
        """
        return self.alias_map.get(key, key)
