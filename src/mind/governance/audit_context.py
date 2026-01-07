# src/mind/governance/audit_context.py

"""
AuditorContext: central view of constitutional artifacts and the knowledge graph
for governance checks and audits.

CONSTITUTIONAL COMPLIANCE:
- Uses IntentRepository for ALL .intent/ access (Mind-Body-Will boundary enforcement)
- Loads Knowledge Graph from Database (SSOT) via KnowledgeService
- NO direct filesystem access to .intent/ subdirectories
- Exposes governance resources via policies dict (loaded from IntentRepository)

FS MUTATION POLICY:
- No direct filesystem mutations outside governed mutation surfaces.
- Runtime artefact writes go through FileHandler (IntentGuard enforced).
- mkdir counts as FS mutation => only FileHandler may create directories.
"""

from __future__ import annotations

import fnmatch
import glob
from collections.abc import Iterable
from functools import cached_property
from pathlib import Path
from typing import Any

from mind.governance.enforcement_loader import EnforcementMappingLoader
from shared.config import Settings, settings
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 55a77b97-fc08-4b0c-b818-97b1158343e9
class AuditorContext:
    """
    Provides access to '.intent' artifacts and the in-memory knowledge graph.

    CONSTITUTIONAL BOUNDARY ENFORCEMENT:
    - All .intent/ access goes through IntentRepository
    - No direct filesystem paths to .intent/ subdirectories
    - Policies loaded via IntentRepository APIs only
    """

    # ID: 4c0f2c62-3d57-4b32-8bff-76a8f3d3fd2f
    def __init__(self, repo_path: Path, settings_instance: Settings | None = None):
        """
        Initialize AuditorContext for a specific repository.

        Args:
            repo_path: Root path of the repository to audit
            settings_instance: Optional Settings instance. If None, uses global settings.
        """
        self.repo_path = repo_path.resolve()

        # Use provided settings or fall back to global
        if settings_instance:
            self.paths = settings_instance.paths
        else:
            self.paths = settings.paths

        self.src_dir = self.paths.repo_root / "src"
        self.intent_path = self.paths.intent_root

        self.last_findings: list[Any] = []
        self.policies: dict[str, Any] = self._load_governance_resources()
        self.enforcement_loader = EnforcementMappingLoader(self.paths.intent_root)

        # Knowledge graph is SSOT from database; file artefact is optional debug output.
        self.knowledge_graph: dict[str, Any] = {"symbols": {}}
        self.symbols_list: list[Any] = []
        self.symbols_map: dict[str, Any] = {}

    @property
    # ID: 2e3a5e67-17c7-4c86-8ad5-8a5bfe1b2b14
    def intent_root(self) -> Path:
        """Convenience alias for intent root."""
        return self.intent_path

    @property
    # ID: 3b95fd8e-69e9-4909-bbbd-bfc2f8c31c1e
    def charter_path(self) -> Path:
        """
        Legacy accessor - DEPRECATED.
        Returns intent_root for backward compatibility.
        New code should use IntentRepository APIs.
        """
        logger.warning(
            "AuditorContext.charter_path is deprecated. Use IntentRepository instead."
        )
        return self.intent_path

    @property
    # ID: 9c7c2ef9-1b23-4c3a-9f4c-8b9d1d0b2e21
    def mind_path(self) -> Path:
        """
        Canonical Mind runtime root.

        IMPORTANT:
        - This is runtime state under var/, not .intent/.
        - We resolve only; we do not create directories here.
        """
        # Use PathResolver (SSOT) to avoid duplicating repo-relative layout knowledge.
        return self.paths.var_dir / "mind"

    # ID: 4a2f2b3d-1a8a-4a1f-9a8e-2b6a0e7d9b3c
    def get_files(
        self,
        include: Iterable[str],
        exclude: Iterable[str] | None = None,
    ) -> list[Path]:
        """
        Deterministically expand repo-relative glob patterns into file Paths.

        CONSTITUTIONAL COMPLIANCE:
        - This method MUST NOT enumerate `.intent/**` at all.
        - This method MUST NOT mutate the filesystem.

        Args:
            include: Repo-relative glob patterns (e.g., "src/**/*.py").
            exclude: Optional repo-relative patterns to exclude.

        Returns:
            Sorted list of absolute Paths.
        """
        root = self.repo_path
        exclude = list(exclude or [])

        # Hard exclusions (policy boundary + performance hygiene)
        hard_excludes = [
            ".intent/**",  # forbidden for direct filesystem access
            ".git/**",
            ".venv/**",
            "venv/**",
            "**/__pycache__/**",
            "var/**",  # runtime artefacts should not be linted/audited as source
            "work/**",
            "reports/**",
        ]

        exclude_patterns = set(exclude) | set(hard_excludes)

        def _is_excluded(rel_posix: str) -> bool:
            """
            Check if a file path matches any exclusion pattern.
            """
            for pat in exclude_patterns:
                pat = pat.replace("\\", "/")

                # Handle standard glob patterns without **
                if "**" not in pat:
                    if fnmatch.fnmatch(rel_posix, pat):
                        return True
                    continue

                # Handle recursive glob patterns
                parts = pat.split("**")

                # FIX: If pattern is just "**", exclude everything (unlikely but safe)
                if not any(parts):
                    return True

                # Prefix check
                if parts[0]:
                    prefix = parts[0].rstrip("/")
                    if not (rel_posix.startswith(prefix + "/") or rel_posix == prefix):
                        continue

                # Suffix check
                if parts[-1] and parts[-1] not in ("", "/"):
                    suffix = parts[-1].lstrip("/")
                    if not (rel_posix.endswith("/" + suffix) or rel_posix == suffix):
                        continue

                # Middle part check (e.g., **/pycache/**)
                # If there are middle parts, the path must contain those segments
                mid_parts = [p.strip("/") for p in parts[1:-1] if p.strip("/")]
                if mid_parts:
                    if not all(mp in rel_posix for mp in mid_parts):
                        continue

                return True

            return False

        matches: set[Path] = set()
        for pattern in include:
            abs_pattern = (root / pattern).as_posix()
            for hit in glob.glob(abs_pattern, recursive=True):
                p = Path(hit)
                if not p.is_file():
                    continue
                try:
                    rel = p.relative_to(root).as_posix()
                    if _is_excluded(rel):
                        continue
                    matches.add(p)
                except ValueError:
                    continue

        return sorted(matches)

    @cached_property
    # ID: 0e0b18cf-2c4a-43f5-8b1b-2a0f3c6d1d51
    def python_files(self) -> list[Path]:
        """
        Canonical set of Python files to be scanned by governance checks.

        Cached per AuditorContext instance to avoid repeated repo scans.
        """
        return self.get_files(include=["src/**/*.py", "tests/**/*.py"])

    # ID: 3d1f1c34-fd1e-4bb8-8b4f-3f9a6c6dfd41
    async def load_knowledge_graph(self) -> None:
        """
        Load knowledge graph from the database (SSOT).
        """
        logger.info(
            "Loading knowledge graph from database (SSOT) for %s...", self.repo_path
        )
        try:
            knowledge_service = KnowledgeService(self.repo_path)
            self.knowledge_graph = await knowledge_service.get_graph()
            self.symbols_map = self.knowledge_graph.get("symbols", {})
            self.symbols_list = list(self.symbols_map.values())
            logger.info(
                "Loaded knowledge graph with %s symbols from database.",
                len(self.symbols_list),
            )
            self._save_knowledge_graph_artifact()
        except Exception as e:
            logger.error("Failed to load knowledge graph from DB: %s", e)
            self.knowledge_graph = {"symbols": {}}
            self.symbols_map = {}
            self.symbols_list = []

    # ID: 6b11bd31-49d6-4f71-93dd-28a1a7b2f4ac
    def _save_knowledge_graph_artifact(self) -> None:
        """
        Save knowledge graph to a runtime artefact location for debugging.
        """
        import json

        try:
            fh = FileHandler(str(self.repo_path))
            reports_rel_dir = "var/reports"
            fh.ensure_dir(reports_rel_dir)
            artifact_rel_path = f"{reports_rel_dir}/knowledge_graph.json"
            payload = json.dumps(self.knowledge_graph, indent=2, default=str)
            fh.write_runtime_text(artifact_rel_path, payload)
        except Exception:
            pass

    # ID: 51b2d7cf-51e4-4c8d-bc34-b5b7d41af7db
    def _load_governance_resources(self) -> dict[str, Any]:
        """
        Load governance resources via IntentRepository.
        """
        resources: dict[str, Any] = {}
        try:
            intent_repo = get_intent_repository()
            for policy_ref in intent_repo.list_policies():
                try:
                    policy_data = intent_repo.load_policy(policy_ref.policy_id)
                    if policy_data is not None:
                        doc_id = policy_data.get("id") or policy_ref.policy_id
                        resources[doc_id] = policy_data
                except Exception:
                    continue
        except Exception as e:
            logger.error("Failed to load governance resources: %s", e)
        return resources


def _to_repo_relative_path(path: Path) -> str:
    """
    Convert an absolute path to a repo-relative POSIX path.
    """
    repo_root = Path(settings.REPO_PATH).resolve()
    resolved = path.resolve()
    if resolved.is_relative_to(repo_root):
        return resolved.relative_to(repo_root).as_posix()
    raise ValueError(f"Path is outside repository boundary: {resolved}")


__all__ = ["AuditorContext"]
