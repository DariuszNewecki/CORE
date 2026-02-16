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

HEALED (V2.3.0):
- "Single-Pass Sensation": Caches the full filesystem scan in memory.
- "Pattern Memoization": Remembers results of glob patterns to avoid 75,000 redundant checks.
- "AST Caching": Shares logic trees across all 82 rules.
"""

from __future__ import annotations

import ast
import fnmatch
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from mind.governance.enforcement_loader import EnforcementMappingLoader
from shared.infrastructure.intent.intent_repository import (
    IntentRepository,
    get_intent_repository,
)
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ============================================================================
# MODULE-LEVEL CACHE
# ============================================================================
# Cache structure: {repo_path_str: {knowledge_graph, symbols_map, symbols_list}}
_KNOWLEDGE_GRAPH_CACHE: dict[str, dict[str, Any]] = {}

# HEALED: Global cache for ASTs to prevent re-parsing during a single run
_AST_CACHE: dict[Path, ast.AST] = {}


# ID: baa7d0a4-2b67-428c-ab64-1e3dbe009b19
def clear_knowledge_graph_cache() -> None:
    """
    Clear the module-level knowledge graph cache.
    """
    global _KNOWLEDGE_GRAPH_CACHE, _AST_CACHE
    _KNOWLEDGE_GRAPH_CACHE.clear()
    _AST_CACHE.clear()
    logger.debug("Knowledge graph and AST caches cleared")


# ============================================================================
# AUDITOR CONTEXT
# ============================================================================


# ID: 55a77b97-fc08-4b0c-b818-97b1158343e9
class AuditorContext:
    """
    Provides access to '.intent' artifacts and the in-memory knowledge graph.
    """

    # ID: 4c0f2c62-3d57-4b32-8bff-76a8f3d3fd2f
    def __init__(
        self,
        repo_path: Path,
        intent_repository: IntentRepository | None = None,
    ):
        self.intent_repo = intent_repository or get_intent_repository()
        self.repo_path = repo_path.resolve()

        # Use PathResolver directly (no settings dependency)
        self.paths = PathResolver(self.repo_path)

        # CONSTITUTIONAL FIX: Initialize EngineRegistry with PathResolver
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

        # HEALED: Sensory Caches for performance optimization
        self._file_list_cache: list[Path] | None = None
        self._rel_path_map: dict[Path, str] = {}
        self._pattern_cache: dict[str, list[Path]] = {}

    @property
    # ID: 2e3a5e67-17c7-4c86-8ad5-8a5bfe1b2b14
    def intent_root(self) -> Path:
        """Convenience alias for intent root."""
        return self.intent_path

    @property
    # ID: 9c7c2ef9-1b23-4c3a-9f4c-8b9d1d0b2e21
    def mind_path(self) -> Path:
        """
        Canonical Mind runtime root.
        """
        return self.paths.var_dir / "mind"

    # ID: 4a2f2b3d-1a8a-4a1f-9a8e-2b6a0e7d9b3c
    def get_files(
        self,
        include: Iterable[str],
        exclude: Iterable[str] | None = None,
    ) -> list[Path]:
        """
        Deterministically expand repo-relative glob patterns into file Paths.
        HEALED: Optimized via Single-Pass Sensation and Memoization.
        """
        # 1. GENERATE CACHE KEY
        include_list = sorted(list(include))
        exclude_list = sorted(list(exclude or []))
        cache_key = f"inc:{include_list}|exc:{exclude_list}"

        # 2. RETURN MEMOIZED RESULT (INSTANT)
        if cache_key in self._pattern_cache:
            return self._pattern_cache[cache_key]

        root = self.repo_path

        # 3. INITIALIZE FILE LIST (COLD START ONLY)
        if self._file_list_cache is None:
            logger.debug("⚡ Cold start: Scanning filesystem once...")
            self._file_list_cache = list(self.repo_path.rglob("*.py"))
            for p in self._file_list_cache:
                self._rel_path_map[p] = str(p.relative_to(root)).replace("\\", "/")

        # 4. PERFORM FILTERING (USING ORIGINAL ROBUST LOGIC)
        hard_excludes = [
            ".intent/**",
            ".git/**",
            ".venv/**",
            "venv/**",
            "**/__pycache__/**",
            "var/**",
            "work/**",
            "reports/**",
        ]
        exclude_patterns = set(exclude_list) | set(hard_excludes)

        def _is_excluded(rel_posix: str) -> bool:
            for pat in exclude_patterns:
                pat = pat.replace("\\", "/")
                if "**" not in pat:
                    if fnmatch.fnmatch(rel_posix, pat):
                        return True
                    continue
                parts = pat.split("**")
                if not any(parts):
                    return True
                if parts[0]:
                    prefix = parts[0].rstrip("/")
                    if not (rel_posix.startswith(prefix + "/") or rel_posix == prefix):
                        continue
                if parts[-1] and parts[-1] not in ("", "/"):
                    suffix = parts[-1].lstrip("/")
                    if not (rel_posix.endswith("/" + suffix) or rel_posix == suffix):
                        continue
                mid_parts = [p.strip("/") for p in parts[1:-1] if p.strip("/")]
                if mid_parts:
                    if not all(mp in rel_posix for mp in mid_parts):
                        continue
                return True
            return False

        matched: set[Path] = set()
        for inc_pattern in include_list:
            # Optimized lookup for the pre-scanned list
            for p in self._file_list_cache:
                rel_posix = self._rel_path_map[p]
                if fnmatch.fnmatch(rel_posix, inc_pattern):
                    if not _is_excluded(rel_posix):
                        matched.add(p)

        result = sorted(matched)
        self._pattern_cache[cache_key] = result  # Memoize for next rule
        return result

    # ID: 182db297-46ce-4b24-9b05-e496f932769c
    # ID: cd8487e5-7382-4242-a54e-dfa7b59d3070
    def get_tree(self, file_path: Path) -> ast.AST | None:
        """HEALED: Retrieve a parsed tree from cache or create it."""
        if file_path in _AST_CACHE:
            return _AST_CACHE[file_path]

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
            _AST_CACHE[file_path] = tree
            return tree
        except Exception as e:
            logger.warning("Failed to parse %s: %s", file_path.name, e)
            return None

    # ID: 3d1f1c34-fd1e-4bb8-8b4f-3f9a6c6dfd41
    async def load_knowledge_graph(self, force: bool = False) -> None:
        """
        Load knowledge graph from the database (SSOT).
        """
        cache_key = str(self.repo_path)
        if not force and cache_key in _KNOWLEDGE_GRAPH_CACHE:
            cached = _KNOWLEDGE_GRAPH_CACHE[cache_key]
            self.knowledge_graph = cached["knowledge_graph"]
            self.symbols_map = cached["symbols_map"]
            self.symbols_list = cached["symbols_list"]
            return

        logger.info("Loading knowledge graph from database (SSOT)...")
        try:
            knowledge_service = KnowledgeService(self.repo_path)
            self.knowledge_graph = await knowledge_service.get_graph()
            self.symbols_map = self.knowledge_graph.get("symbols", {})
            self.symbols_list = list(self.symbols_map.values())
            _KNOWLEDGE_GRAPH_CACHE[cache_key] = {
                "knowledge_graph": self.knowledge_graph,
                "symbols_map": self.symbols_map,
                "symbols_list": self.symbols_list,
            }
        except Exception as e:
            logger.error("Failed to load knowledge graph from DB: %s", e)
            self.knowledge_graph = {"symbols": {}}
            self.symbols_map = {}
            self.symbols_list = []

    # ID: 51b2d7cf-51e4-4c8d-bc34-b5b7d41af7db
    def _load_governance_resources(self) -> dict[str, Any]:
        """
        Load governance resources via IntentRepository.
        """
        resources: dict[str, Any] = {}
        try:
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


__all__ = ["AuditorContext", "clear_knowledge_graph_cache"]
