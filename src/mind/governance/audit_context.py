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
- Mind layer MUST NOT write to filesystem.
- FileHandler usage removed to comply with architecture.mind.no_filesystem_writes.

PERFORMANCE:
- Module-level knowledge graph cache per repo_path
- Cache persists for process lifetime unless explicitly cleared
- Thread-safe for async-only usage (no thread locking)
"""

from __future__ import annotations

import fnmatch
import glob
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from mind.governance.enforcement_loader import EnforcementMappingLoader
from shared.infrastructure.intent.intent_repository import (
    IntentRepository,
    get_intent_repository,
)
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService

# REMOVED: from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger

# REMOVED: from shared.config import Settings, settings
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ============================================================================
# MODULE-LEVEL CACHE
# ============================================================================
# Cache structure: {repo_path_str: {knowledge_graph, symbols_map, symbols_list}}
# Cache lifetime: Process lifetime (until explicit clear_cache() call)
# Thread safety: Async-only (no thread locking required)
_KNOWLEDGE_GRAPH_CACHE: dict[str, dict[str, Any]] = {}


# ID: baa7d0a4-2b67-428c-ab64-1e3dbe009b19
def clear_knowledge_graph_cache() -> None:
    """
    Clear the module-level knowledge graph cache.

    Use cases:
    - Test teardown to ensure clean state
    - After `core-admin knowledge sync` rebuilds the graph
    - When you need to force reload from database

    This is thread-safe for async usage (no locking needed).
    """
    global _KNOWLEDGE_GRAPH_CACHE
    _KNOWLEDGE_GRAPH_CACHE.clear()
    logger.debug("Knowledge graph cache cleared")


# ============================================================================
# AUDITOR CONTEXT
# ============================================================================


# ID: 55a77b97-fc08-4b0c-b818-97b1158343e9
class AuditorContext:
    """
    Provides access to '.intent' artifacts and the in-memory knowledge graph.

    CONSTITUTIONAL BOUNDARY ENFORCEMENT:
    - All .intent/ access goes through IntentRepository
    - No direct filesystem paths to .intent/ subdirectories
    - Policies loaded via IntentRepository APIs only

    PERFORMANCE:
    - Knowledge graph cached at module level per repo_path
    - Multiple AuditorContext instances share same cache
    - Cache invalidation via clear_knowledge_graph_cache() function
    """

    # ID: 4c0f2c62-3d57-4b32-8bff-76a8f3d3fd2f
    def __init__(
        self,
        repo_path: Path,
        # Removed settings_instance as it caused circular deps
        intent_repository: IntentRepository | None = None,
    ):
        """
        Initialize AuditorContext for a specific repository.

        Args:
            repo_path: Root path of the repository to audit
            intent_repository: Optional IntentRepository instance. If None, uses global instance.
        """
        self.intent_repo = intent_repository or get_intent_repository()
        self.repo_path = repo_path.resolve()

        # REFACTORED: Use PathResolver directly instead of settings
        self.paths = PathResolver(self.repo_path)

        # CONSTITUTIONAL FIX: Initialize EngineRegistry with PathResolver
        # This must happen at Mind bootstrap, not at execution time.
        # The Mind layer (AuditorContext) initializes Body layer infrastructure (EngineRegistry).
        # This ensures engines are ready for ANY audit operation (full audit, filtered audit, etc.)
        from mind.logic.engines.registry import EngineRegistry

        EngineRegistry.initialize(self.paths)
        logger.debug("EngineRegistry initialized via AuditorContext bootstrap")

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

                # FIXED: Suffix check with proper matching logic
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

        # Expand include patterns
        matched: set[Path] = set()
        for inc_pattern in include:
            # UNIX-style glob expansion
            pattern_path = str(root / inc_pattern)
            for match_str in glob.glob(pattern_path, recursive=True):
                match_p = Path(match_str).resolve()

                # Ensure it's actually under the repo root
                try:
                    rel = match_p.relative_to(root)
                except ValueError:
                    # Outside repo boundary - skip
                    continue

                rel_posix = rel.as_posix()

                # Skip excluded paths
                if _is_excluded(rel_posix):
                    continue

                # Only include files (not directories)
                if match_p.is_file():
                    matched.add(match_p)

        return sorted(matched)

    # ID: 3d1f1c34-fd1e-4bb8-8b4f-3f9a6c6dfd41
    async def load_knowledge_graph(self, force: bool = False) -> None:
        """
        Load knowledge graph from the database (SSOT).

        Uses module-level cache to avoid redundant DB queries across multiple
        AuditorContext instances (e.g., in test suites).

        Args:
            force: If True, bypass cache and reload from database. Default False.

        Performance:
        - First call: Loads from DB (~1.5s for 1449 symbols)
        - Subsequent calls: Loads from cache (~0ms)
        - Cache shared across all AuditorContext instances for same repo_path
        - Cache persists for process lifetime unless cleared via clear_knowledge_graph_cache()
        """
        cache_key = str(self.repo_path)

        # PERFORMANCE FIX: Check module-level cache first
        if not force and cache_key in _KNOWLEDGE_GRAPH_CACHE:
            cached = _KNOWLEDGE_GRAPH_CACHE[cache_key]
            self.knowledge_graph = cached["knowledge_graph"]
            self.symbols_map = cached["symbols_map"]
            self.symbols_list = cached["symbols_list"]
            logger.debug(
                "Knowledge graph loaded from cache (%d symbols) for %s",
                len(self.symbols_list),
                self.repo_path,
            )
            return

        # Cache miss or force reload - load from database
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

            # Cache the successful load
            _KNOWLEDGE_GRAPH_CACHE[cache_key] = {
                "knowledge_graph": self.knowledge_graph,
                "symbols_map": self.symbols_map,
                "symbols_list": self.symbols_list,
            }

            # REMOVED: _save_knowledge_graph_artifact() call.
            # Writing debug artifacts is a side-effect not permitted in the Mind layer.

        except Exception as e:
            logger.error("Failed to load knowledge graph from DB: %s", e)
            # Don't cache errors - set empty state and allow retry
            self.knowledge_graph = {"symbols": {}}
            self.symbols_map = {}
            self.symbols_list = []

    # ID: 51b2d7cf-51e4-4c8d-bc34-b5b7d41af7db
    def _load_governance_resources(self) -> dict[str, Any]:
        """
        Load governance resources via IntentRepository.

        Uses the instance's intent_repo (from constructor) instead of
        calling get_intent_repository() again for consistency.
        """
        resources: dict[str, Any] = {}
        try:
            # Use self.intent_repo instead of get_intent_repository()
            for policy_ref in self.intent_repo.list_policies():
                try:
                    policy_data = self.intent_repo.load_policy(policy_ref.policy_id)
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
    # Note: Accessing global settings is avoided here since we can't reliably get repo_path
    # context in a standalone function without an argument.
    # However, this function isn't used in the class above anymore.
    # If needed, it should take repo_root as an argument.
    raise NotImplementedError("_to_repo_relative_path requires repo_root context")


__all__ = ["AuditorContext", "clear_knowledge_graph_cache"]
