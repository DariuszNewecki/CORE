# src/core/intent_model.py
"""IntentModel: domain structure loader and helpers.

This module reads `.intent/knowledge/source_structure.yaml` and exposes helpers to:
- Inspect the normalized domain structure.
- Resolve a file path to its domain.
- Read domain-to-domain allowed import bridges.

The loader is robust to either top-level key: `structure:` (current) or `domains:` (alternate).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from shared.logger import getLogger
from shared.path_utils import get_repo_root

log = getLogger(__name__)


class IntentModel:
    """Load and normalize CORE's source/domain structure."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        """Initialize the intent model.

        Args:
            project_root: Optional project root to anchor lookups. If not provided,
                the repository root is discovered via ``get_repo_root()``.
        """
        self.repo_root: Path = (project_root or get_repo_root()).resolve()
        self.structure: Dict[str, Dict[str, Any]] = self._load_structure()

    # -----------------------------
    # Public API
    # -----------------------------
    def resolve_domain_for_path(self, file_path: Path) -> Optional[str]:
        """Resolve a source file path to its owning domain.

        Chooses the *deepest* matching domain path if overlaps ever occur.

        Args:
            file_path: Absolute or relative path to a source file.

        Returns:
            The domain name (e.g., ``"core"``) or ``None`` when no domain matches.
        """
        path = Path(file_path).resolve()

        best_match: Optional[str] = None
        best_len = -1

        for domain, info in self.structure.items():
            domain_rel = info.get("path")
            if not domain_rel:
                continue

            domain_abs = (self.repo_root / domain_rel).resolve()
            try:
                path.relative_to(domain_abs)  # within domain folder?
            except ValueError:
                continue
            else:
                plen = len(domain_abs.as_posix())
                if plen > best_len:
                    best_len = plen
                    best_match = domain

        return best_match

    def get_domain_permissions(self, domain: str) -> List[str]:
        """Return domain-level allowed import bridges for a given domain.

        The underlying YAML may include lists of standard/third-party libraries.
        This method filters those out and returns **only other domain names**.

        Args:
            domain: Domain to inspect (e.g., ``"core"``).

        Returns:
            A list of domain names that ``domain`` is allowed to import.
        """
        info = self.structure.get(domain, {})
        allowed = info.get("allowed_imports") or []

        flat = list(self._flatten(allowed))
        domains: List[str] = []
        known = set(self.structure.keys())

        for item in flat:
            if isinstance(item, str) and item in known and item not in domains:
                domains.append(item)

        return domains

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _flatten(self, xs):
        """Yield a flattened stream of items from (possibly nested) lists/tuples.

        Args:
            xs: Iterable that may contain nested lists/tuples.

        Yields:
            Individual items with all list/tuple nesting removed.
        """
        for x in xs:
            if isinstance(x, (list, tuple)):
                yield from self._flatten(x)
            else:
                yield x

    def _load_structure(self) -> Dict[str, Dict[str, Any]]:
        """Load and normalize the source structure from YAML.

        Supports:
            - ``{"structure": [ ...entries... ]}``
            - ``{"domains":   [ ...entries... ]}``
            - A bare list ``[ ...entries... ]``
            - A map form ``{"domains": {"core": {...}, ...}}``

        Returns:
            A normalized mapping: ``{domain: {"path": str, "allowed_imports": list}}``.
        """
        cfg_path = self.repo_root / ".intent" / "knowledge" / "source_structure.yaml"
        if not cfg_path.exists():
            log.warning(
                "Source structure file not found at %s; proceeding with empty structure.",
                cfg_path,
            )
            return {}

        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # pragma: no cover (defensive)
            log.error("Failed to load %s: %s", cfg_path, exc)
            return {}

        # Accept both shapes:
        # - {"structure": [ ...entries... ]}
        # - {"domains":   [ ...entries... ]}
        # - or even just a YAML list [ ...entries... ]
        entries: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            if "structure" in data and isinstance(data["structure"], list):
                entries = data["structure"]
            elif "domains" in data and isinstance(data["domains"], list):
                entries = data["domains"]
            elif isinstance(data.get("domains"), dict):
                # tolerate map form: {"domains": {"core": {...}, ...}}
                for dname, dinfo in (data.get("domains") or {}).items():
                    if isinstance(dinfo, dict):
                        dinfo = {"domain": dname, **dinfo}
                        entries.append(dinfo)
        elif isinstance(data, list):
            entries = data  # bare list

        normalized: Dict[str, Dict[str, Any]] = {}
        for item in entries:
            if not isinstance(item, dict):
                continue
            name = item.get("domain")
            path = item.get("path")
            if not name or not path:
                continue

            allowed = item.get("allowed_imports") or []
            # Normalize allowed_imports to a list[str]
            if isinstance(allowed, str):
                allowed = [allowed]
            elif not isinstance(allowed, list):
                allowed = []

            normalized[name] = {
                "path": path,
                "allowed_imports": allowed,
            }

        if not normalized:
            log.warning(
                "No valid domain entries parsed from %s; got %r", cfg_path, data
            )

        return normalized
