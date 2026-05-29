# src/mind/governance/audit_context.py

"""
AuditorContext: central view of constitutional artifacts and the knowledge graph
for governance checks and audits.

Constitutional Alignment:
- Uses IntentRepository for ALL .intent/ access (Mind-Body-Will boundary enforcement)
- Loads Knowledge Graph from Database (SSOT) via KnowledgeService
- NO direct filesystem access to .intent/ subdirectories
- Exposes governance resources via policies dict (loaded from IntentRepository)
- Mind layer MUST NOT write to filesystem

Performance:
- Module-level knowledge graph cache per repo_path
- Single-pass filesystem scan with pattern memoization
- AST cache shared across all rules within a single run
- Cache persists for process lifetime unless explicitly cleared
"""

from __future__ import annotations

import ast
import fnmatch
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mind.governance.enforcement_loader import EnforcementMappingLoader
from shared.infrastructure.intent.intent_repository import (
    IntentRepository,
    get_intent_repository,
)
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.protocols.knowledge import SessionProviderProtocol


if TYPE_CHECKING:
    from shared.infrastructure.llm.client import LLMClient
    from shared.protocols.knowledge import SessionProviderProtocol


logger = getLogger(__name__)


# ============================================================================
# MODULE-LEVEL CACHE
# ============================================================================
# Cache structure: {repo_path_str: {knowledge_graph, symbols_map, symbols_list}}
_KNOWLEDGE_GRAPH_CACHE: dict[str, dict[str, Any]] = {}
_AST_CACHE: dict[Path, ast.AST] = {}


# ADR-076 D5: structural excludes are directory names whose contents are
# never the subject of any governance rule — VCS metadata, virtualenvs,
# bytecode caches, third-party dependency mirrors, packaging output. They
# are the minimum prune the candidate walker performs *before* the
# rule-scope filter. ``work/`` and ``reports/`` are deliberately NOT
# listed: they are application output, and the derived walker correctly
# admits them iff some active per-file rule scopes them. The diagnostic
# (``audit_walker_diagnostic`` below) reports if any active per-file rule
# scopes into a listed structural dir — that would be a real finding.
_STRUCTURAL_DIR_PARTS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
    }
)


def _is_under_structural_exclude(p: Path, root: Path) -> bool:
    """Return True if ``p`` falls under a structural-excluded directory.

    Component check on the relative path; cheaper than fnmatch on every
    file at scan time.
    """
    try:
        rel = p.relative_to(root)
    except ValueError:
        return False
    return any(part in _STRUCTURAL_DIR_PARTS for part in rel.parts)


def _include_matches(rel_posix: str, pattern: str) -> bool:
    """Match ``rel_posix`` against ``pattern`` with correct ``**`` semantics.

    For patterns without ``**``, behaviour is identical to
    ``fnmatch.fnmatch``. For patterns containing ``**/`` or ``/**``, the
    ``**/``- and ``/**``-collapsed forms are also tried — this restores
    the zero-intermediate-directory case (e.g. ``src/api/main.py``
    matches ``src/api/**/*.py``).

    Lifted to module scope (ADR-076 D5) so both the candidate-retention
    pass during file-cache build AND the per-rule scope filter at dispatch
    consult the same matcher. Single source for "does this path satisfy
    this scope" — the walker and the dispatcher can never disagree about
    whether a file is in scope.
    """
    if fnmatch.fnmatch(rel_posix, pattern):
        return True
    if "**/" in pattern and fnmatch.fnmatch(rel_posix, pattern.replace("**/", "")):
        return True
    if "/**" in pattern and fnmatch.fnmatch(rel_posix, pattern.replace("/**", "")):
        return True
    return False


# NOTE: zero call sites in src/ — candidate for removal.
# Retained until ADR-049 ritual permits removal.
# ID: baa7d0a4-2b67-428c-ab64-1e3dbe009b19
def clear_knowledge_graph_cache() -> None:
    """Clear the module-level knowledge graph and AST caches."""
    global _KNOWLEDGE_GRAPH_CACHE, _AST_CACHE
    _KNOWLEDGE_GRAPH_CACHE.clear()
    _AST_CACHE.clear()
    logger.debug("Knowledge graph and AST caches cleared")


# ============================================================================
# AUDITOR CONTEXT
# ============================================================================


# ID: 55a77b97-fc08-4b0c-b818-97b1158343e9
class AuditorContext:
    """Provides access to .intent artifacts and the in-memory knowledge graph."""

    # ID: 4c0f2c62-3d57-4b32-8bff-76a8f3d3fd2f
    def __init__(
        self,
        repo_path: Path,
        intent_repository: IntentRepository | None = None,
        session_provider: SessionProviderProtocol | None = None,
        llm_client: LLMClient | None = None,
    ):
        self.session_provider = session_provider
        self.intent_repo = intent_repository or get_intent_repository()
        self.repo_path = repo_path.resolve()
        self.llm_client = llm_client

        self.paths = PathResolver(self.repo_path)

        from mind.logic.engines.registry import EngineRegistry

        # #306: wire an LLM client into the EngineRegistry if one was
        # supplied. When None (no provider configured / LLM disabled),
        # the registry transparently falls back to LLMGateStubEngine.
        # rule_executor.py surfaces that fall-back as a per-rule warning
        # so the audit output is never silent about a muted check (#307).
        EngineRegistry.initialize(self.paths, llm_client=self.llm_client)
        logger.debug(
            "EngineRegistry initialized via AuditorContext bootstrap (llm_client=%s)",
            "wired" if self.llm_client else "stub-fallback",
        )

        self.src_dir = self.paths.repo_root / "src"
        self.intent_path = self.paths.intent_root

        self.last_findings: list[Any] = []
        self.policies: dict[str, Any] = self._load_governance_resources()
        self.enforcement_loader = EnforcementMappingLoader(self.paths.intent_root)

        self.knowledge_graph: dict[str, Any] = {"symbols": {}}
        self.symbols_list: list[Any] = []
        self.symbols_map: dict[str, Any] = {}

        # Sensory caches for performance
        self._file_list_cache: list[Path] | None = None
        self._rel_path_map: dict[Path, str] = {}
        self._pattern_cache: dict[str, list[Path]] = {}
        # ADR-076 D5: union of active per-file rule scopes, computed
        # lazily on first get_files() call and reset by invalidate_file_cache.
        self._per_file_scopes_cache: list[str] | None = None

        # ADR-044: per-run knobs for the llm_gate verdict cache. The
        # rule_executor reads force_llm via getattr; engines that don't
        # consult them ignore them. _llm_gate_cache_swept is the one-shot
        # latch that ensures sweep_llm_gate_cache() does its DELETE at most
        # once per audit run.
        self.force_llm: bool = False
        self._llm_gate_cache_swept: bool = False

    @property
    # ID: 2e3a5e67-17c7-4c86-8ad5-8a5bfe1b2b14
    def intent_root(self) -> Path:
        """Convenience alias for intent root."""
        return self.intent_path

    @property
    # ID: 9c7c2ef9-1b23-4c3a-9f4c-8b9d1d0b2e21
    def mind_path(self) -> Path:
        """Canonical Mind runtime root."""
        return self.paths.var_dir / "mind"

    # ID: 7d3e8c2a-9f4b-4c1d-8e6a-2b7f9d5c3a1e
    def invalidate_file_cache(self) -> None:
        """Clear cached filesystem scan and per-pattern subsets.

        Called at the entry of every audit run so newly-committed files
        become visible to the next cycle without daemon restart (ADR-039).
        Within a single run, the rebuilt cache is still shared across rules.
        """
        self._file_list_cache = None
        self._rel_path_map.clear()
        self._pattern_cache.clear()
        # ADR-076 D5: the cached scope union is derived from policies +
        # enforcement_loader; both can change on reload_governance, so
        # invalidate alongside the file cache.
        self._per_file_scopes_cache = None
        # ADR-039 supplement 2026-05-16: clear parsed-tree cache so
        # ast_gate rules evaluate post-write content, not prior-cycle
        # ASTs. Race surface (shared AuditorContext across sensors) is
        # identical to _file_list_cache — degraded perf on collision,
        # not correctness.
        _AST_CACHE.clear()

    # ID: 2704ca91-45bd-420e-be0b-d3f4bb798683
    def reload_governance(self) -> None:
        """Re-read policies and enforcement mappings from disk.

        Called at the entry of every audit run so .intent/ edits made
        since the last cycle (new rules, new mappings, new contracts)
        become enforceable without daemon restart (ADR-039). Mirrors
        invalidate_file_cache(): both refresh inputs the cached
        AuditorContext would otherwise hold across the daemon lifetime.
        """
        self.intent_repo.reload()
        self.policies = self._load_governance_resources()
        self.enforcement_loader = EnforcementMappingLoader(self.paths.intent_root)

    # ID: 3e8a1b6c-5d4f-49a2-b71c-8e2d0f4a9c5b
    async def sweep_llm_gate_cache(self) -> int:
        """Delete llm_gate_verdicts rows past their TTL (ADR-044).

        Called by the audit driver at the start of each run. The latch
        ``_llm_gate_cache_swept`` ensures the DELETE fires at most once per
        AuditorContext, even when callers (auditor + filtered_audit) both
        invoke it as a safety net.

        Returns the count of rows deleted.

        TTL value source order:
          1. operational_config.audit.llm_gate_verdict_cache_ttl_days
          2. literal default of 30 days (placeholder until Step 6 lands)
        """
        if self._llm_gate_cache_swept:
            return 0
        self._llm_gate_cache_swept = True

        # ADR-044 §Decision: TTL is hygiene, not correctness. Hash mismatch
        # is the correctness mechanism. So an unavailable config or DB
        # session must NOT block the audit — it falls through silently.
        try:
            from shared.infrastructure.intent.operational_config import (
                load_operational_config,
            )

            cfg = load_operational_config()
            ttl_days = int(
                getattr(
                    getattr(cfg, "audit", object()),
                    "llm_gate_verdict_cache_ttl_days",
                    30,
                )
            )
        except Exception:
            ttl_days = 30

        # Session is injected by the audit driver before this runs (see
        # auditor.run_full_audit_async + audit.py CLI). When absent (e.g.
        # filtered_audit invoked without an outer session block), TTL sweep
        # is a no-op — the next audit run will catch up.
        session = getattr(self, "db_session", None)
        if session is None:
            return 0

        try:
            from sqlalchemy import text

            result = await session.execute(
                text(
                    "DELETE FROM core.llm_gate_verdicts "
                    "WHERE evaluated_at < NOW() - make_interval(days => :days)"
                ),
                {"days": ttl_days},
            )
            purged = result.rowcount or 0
            await session.commit()
            if purged:
                logger.info(
                    "AuditorContext: TTL-swept %d llm_gate_verdicts row(s) "
                    "older than %d days",
                    purged,
                    ttl_days,
                )
            return purged
        except Exception as exc:
            logger.warning(
                "AuditorContext: llm_gate_verdicts TTL sweep skipped: %s", exc
            )
            return 0

    # ID: 6f8c2a9b-5e3d-4f17-91c4-2a8b6e5d3f10
    def _active_per_file_rule_scopes(self) -> list[str]:
        """Union of include-patterns from every active per-file rule.

        ADR-076 D5. The walked set is derived from this union: a file is
        retained iff some active per-file rule's scope matches it. By
        lazy-evaluating against ``self.policies`` and
        ``self.enforcement_loader``, ``AuditorContext`` owns the cache
        AND the constraint that shapes it — no caller has to remember to
        feed scopes in, and the derivation cannot fall out of sync with
        the rule set the same context is about to dispatch.

        Context-level rules (``is_context_level=True``) are excluded:
        they use ``verify_context`` and do not iterate the walked set,
        so widening the walk on their behalf would silently re-introduce
        the over-walking the ADR rejects. ``requires_findings_from``
        pre-selectors do not change scope membership; they only narrow
        which files in scope are iterated at dispatch.
        """
        if self._per_file_scopes_cache is not None:
            return self._per_file_scopes_cache

        from mind.governance.rule_extractor import extract_executable_rules

        rules = extract_executable_rules(self.policies, self.enforcement_loader)
        scopes: set[str] = set()
        for r in rules:
            if r.is_context_level:
                continue
            for pat in r.scope:
                if isinstance(pat, str) and pat:
                    scopes.add(pat)
        self._per_file_scopes_cache = sorted(scopes)
        return self._per_file_scopes_cache

    # ID: 4a2f2b3d-1a8a-4a1f-9a8e-2b6a0e7d9b3c
    def get_files(
        self,
        include: Iterable[str],
        exclude: Iterable[str] | None = None,
    ) -> list[Path]:
        """
        Deterministically expand repo-relative glob patterns into file Paths.

        ADR-076 D5: the file-list cache is the DERIVED set
        ``{ f : f matches some active per-file rule's scope }``. After
        pruning a minimal structural-exclude set (.git, .venv,
        __pycache__, node_modules, dist, build) from the candidate walk,
        each candidate is retained iff at least one active per-file rule
        would match it under ``_include_matches`` — the same matcher
        dispatch uses. This is a single-source-of-truth derivation: a
        rule cannot be silently inerted by walker scope (#480) because
        the walker's scope IS the union of rule scopes.

        Per-call behaviour is unchanged: the rule's own ``include``
        patterns narrow the cached set to that rule's working scope.

        Glob semantics:
        - ``*`` matches any run of characters (fnmatch default, may cross ``/``).
        - ``**`` zero-directory semantics handled by ``_include_matches``
          (module-level), shared with the cache builder so dispatch and
          retention agree byte-for-byte on scope membership.
        """
        include_list = sorted(list(include))
        exclude_list = sorted(list(exclude or []))
        cache_key = f"inc:{include_list}|exc:{exclude_list}"

        if cache_key in self._pattern_cache:
            return self._pattern_cache[cache_key]

        root = self.repo_path

        if self._file_list_cache is None:
            logger.debug("⚡ Cold start: Scanning filesystem once...")
            # ADR-076 D5: candidate walk — only structural excludes
            # prune the rglob result. Extensions, application roots, and
            # exclusion of subtrees like ``.intent/`` or ``var/`` are NOT
            # hardcoded here; the retention pass below derives them from
            # the active per-file rules' scopes.
            per_file_scopes = self._active_per_file_rule_scopes()
            self._file_list_cache = []
            for p in self.repo_path.rglob("*"):
                if not p.is_file():
                    continue
                if _is_under_structural_exclude(p, root):
                    continue
                rel_posix = str(p.relative_to(root)).replace("\\", "/")
                # Retain iff some active per-file rule scopes this path.
                if any(_include_matches(rel_posix, sc) for sc in per_file_scopes):
                    self._file_list_cache.append(p)
                    self._rel_path_map[p] = rel_posix

        exclude_patterns = set(exclude_list)

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
            for p in self._file_list_cache:
                rel_posix = self._rel_path_map[p]
                if _include_matches(rel_posix, inc_pattern):
                    if not _is_excluded(rel_posix):
                        matched.add(p)

        result = sorted(matched)
        self._pattern_cache[cache_key] = result
        return result

    # ID: 182db297-46ce-4b24-9b05-e496f932769c
    def get_tree(self, file_path: Path) -> ast.AST | None:
        """Retrieve a parsed AST from cache, or parse and cache on first access."""
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
        """Load knowledge graph from the database (SSOT)."""
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
        """Load governance resources via IntentRepository."""
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
