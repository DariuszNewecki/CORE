# src/mind/logic/engines/knowledge_gate.py

"""
Knowledge Graph Governance Engine.

REFACTORED:
- Handles "core.vector_index" vs "core.symbol_vector_links" schema drift.
- Improved robustness for missing tables.
V2.1: Added orphan_file_check — import graph traversal from declared entry points.
V2.2: Added constitutional table name whitelist — prevents SQL injection via YAML.
"""

from __future__ import annotations

import ast
import fnmatch
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from mind.logic.engines._knowledge_gate_duplication import (
    _check_ast_duplication,
    _check_semantic_duplication,
)
from mind.logic.engines.base import BaseEngine, EngineResult
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
logger = getLogger(__name__)


# ID: 8d880004-d06c-43ba-b15e-9c934097e409
class KnowledgeGateEngine(BaseEngine):
    """
    Context-Aware Knowledge Graph Auditor.
    """

    engine_id = "knowledge_gate"

    # Constitutional whitelist of tables this engine may query.
    # Table names in SQL cannot be parameterized — they must be validated
    # against a known-good set before interpolation.
    # In a self-modifying system, YAML-sourced table names are a supply-chain
    # risk: an adversarially crafted proposal could inject arbitrary SQL via
    # the enforcement mapping. This whitelist closes that window.
    # To add a new table: amend this constant AND submit a constitutional proposal.
    _ALLOWED_TABLES: frozenset[str] = frozenset(
        {
            "core.symbol_vector_links",
            "core.vector_index",  # legacy alias — shim converts to symbol_vector_links below
            "core.cli_commands",
            "core.llm_resources",
            "core.cognitive_roles",
            "core.domains",
        }
    )

    @classmethod
    # ID: 301b31bb-1c1c-4c1e-8bb6-3880f1a1dd4d
    def supported_check_types(cls) -> set[str]:
        return {
            "capability_assignment",
            "ast_duplication",
            "semantic_duplication",
            "duplicate_ids",
            "table_has_records",
            "orphan_file_check",
        }

    # ID: d2fa4e12-5198-462f-9615-0d286c200529
    def verify(self, file_path, params: dict[str, Any]) -> EngineResult:
        return EngineResult(
            ok=False,
            message="KnowledgeGateEngine requires AuditorContext.",
            violations=["Internal: knowledge_gate called without context"],
            engine_id=self.engine_id,
        )

    # ID: 21f029ae-a97d-4000-8372-4f813b400ea4
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        check_type = params.get("check_type")
        if not check_type:
            return []

        check_type = check_type.strip()

        if check_type == "capability_assignment":
            return self._check_capability_assignment(context, params)
        elif check_type == "ast_duplication":
            return _check_ast_duplication(context, params)
        elif check_type == "semantic_duplication":
            return await _check_semantic_duplication(context, params)
        elif check_type == "duplicate_ids":
            return self._check_duplicate_ids(context, params)
        elif check_type == "table_has_records":
            return await self._check_table_has_records(context, params)
        elif check_type == "orphan_file_check":
            return self._check_orphan_files(context, params)

        return []

    async def _check_table_has_records(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        table_name = params.get("table")

        if not table_name:
            return []

        # SCHEMA DRIFT SHIM:
        # Policy says 'core.vector_index', but database uses 'core.symbol_vector_links'
        if table_name == "core.vector_index":
            table_name = "core.symbol_vector_links"

        # CONSTITUTIONAL WHITELIST:
        # Table names cannot be parameterized in SQL — validate against known-good set
        # before interpolation. Closes the supply-chain window where an autonomous
        # proposal could modify an enforcement mapping YAML to inject SQL via table name.
        if table_name not in self._ALLOWED_TABLES:
            findings.append(
                AuditFinding(
                    check_id="knowledge_gate.table_not_whitelisted",
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"Table '{table_name}' is not in the constitutional whitelist. "
                        "Add it to KnowledgeGateEngine._ALLOWED_TABLES via a governed proposal."
                    ),
                    file_path="DB",
                )
            )
            return findings

        db_session = getattr(context, "db_session", None)
        if not db_session:
            return findings

        try:
            query = text(f"SELECT EXISTS(SELECT 1 FROM {table_name} LIMIT 1)")
            result = await db_session.execute(query)
            exists = result.scalar()

            if not exists:
                findings.append(
                    AuditFinding(
                        check_id="knowledge_gate.table_has_records",
                        severity=AuditSeverity.ERROR,
                        message=f"DB SSOT table '{table_name}' is empty.",
                        file_path="DB",
                    )
                )
        except Exception as e:
            # UndefinedTableError handled gracefully
            if "does not exist" in str(e):
                findings.append(
                    AuditFinding(
                        check_id="knowledge_gate.table_missing",
                        severity=AuditSeverity.ERROR,
                        message=f"Constitutional table '{table_name}' is missing from schema.",
                        file_path="DB",
                    )
                )
            else:
                logger.error("Failed to check table '%s': %s", table_name, e)

        return findings

    def _check_duplicate_ids(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        id_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for symbol_data in context.symbols_map.values():
            uuid_val = symbol_data.get("key")
            if uuid_val and uuid_val != "unassigned":
                id_map[uuid_val].append(symbol_data)
        for uuid_val, occurrences in id_map.items():
            if len(occurrences) > 1:
                locs = [
                    f"{s.get('file_path')}:{s.get('line_number', '?')}"
                    for s in occurrences
                ]
                findings.append(
                    AuditFinding(
                        check_id="linkage.duplicate_ids",
                        severity=AuditSeverity.ERROR,
                        message=f"Duplicate ID '{uuid_val}' found.",
                        file_path=occurrences[0].get("file_path"),
                        context={"duplicates": locs},
                    )
                )
        return findings

    def _check_capability_assignment(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        exclude_patterns = params.get("exclude_patterns", ["tests/", "scripts/"])
        for symbol_data in context.symbols_map.values():
            if not symbol_data.get("is_public") or symbol_data.get(
                "name", ""
            ).startswith("_"):
                continue
            if any(p in symbol_data.get("file_path", "") for p in exclude_patterns):
                continue
            if symbol_data.get("key") == "unassigned":
                findings.append(
                    AuditFinding(
                        check_id="linkage.capability.unassigned",
                        severity=AuditSeverity.ERROR,
                        message=f"Public symbol '{symbol_data.get('name')}' has capability='unassigned'.",
                        file_path=symbol_data.get("file_path"),
                        line_number=symbol_data.get("line_number"),
                    )
                )
        return findings

    # ID: kg-orphan-check
    def _check_orphan_files(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Detects source files unreachable from any declared entry point via
        the import graph. Closes the gap left by vulture's symbol-level analysis.
        """
        findings: list[AuditFinding] = []

        repo_path = context.repo_path
        entry_point_dirs = params.get("entry_points")
        if not entry_point_dirs:
            logger.error(
                "orphan_file_check called without entry_points param — "
                "cannot proceed safely, skipping."
            )
            return findings
        exclude_patterns = params.get(
            "excludes",
            [
                "src/**/__init__.py",
                "src/**/__main__.py",
                "src/**/conftest.py",
            ],
        )

        src_root = repo_path / "src"
        if not src_root.exists():
            logger.warning("orphan_file_check: src/ not found at %s", src_root)
            return findings

        # 1. Collect all Python files under src/
        all_files: set[Path] = set(src_root.rglob("*.py"))

        # 2. Filter out excluded patterns
        # ID: 51b8b5d5-9742-4412-87dc-e3ac585bd94e
        def is_excluded(path: Path) -> bool:
            rel = str(path.relative_to(repo_path))
            return any(fnmatch.fnmatch(rel, pat) for pat in exclude_patterns)

        candidate_files = {f for f in all_files if not is_excluded(f)}

        # 3. Resolve entry point files
        seeds: set[Path] = set()
        for ep in entry_point_dirs:
            ep_path = repo_path / ep
            if ep_path.is_dir():
                seeds.update(ep_path.rglob("*.py"))
            elif ep_path.is_file():
                seeds.add(ep_path)

        if not seeds:
            logger.warning(
                "orphan_file_check: no entry point files found in %s", entry_point_dirs
            )
            return findings

        # 4. Build import graph via AST traversal
        # ID: e3057022-9b5d-4e38-a71b-01e92b47e96d
        def resolve_import(module_name: str, current_file: Path) -> Path | None:
            """Resolve a dotted module name to an absolute file path."""
            parts = module_name.split(".")
            # Try absolute from src/
            candidate = src_root.joinpath(*parts).with_suffix(".py")
            if candidate.exists():
                return candidate
            # Try as package __init__
            init_candidate = src_root.joinpath(*parts, "__init__.py")
            if init_candidate.exists():
                return init_candidate
            # Try relative from current file's directory
            rel_candidate = current_file.parent.joinpath(*parts).with_suffix(".py")
            if rel_candidate.exists():
                return rel_candidate
            return None

        # ID: 0096be73-23f5-4bcc-b521-4befdaa4c860
        def get_imports(file_path: Path) -> list[Path]:
            """Extract all local imports from a Python file via AST."""
            imports: list[Path] = []
            try:
                tree = ast.parse(
                    file_path.read_text(encoding="utf-8"), filename=str(file_path)
                )
            except (SyntaxError, OSError):
                return imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        resolved = resolve_import(alias.name, file_path)
                        if resolved:
                            imports.append(resolved)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        resolved = resolve_import(node.module, file_path)
                        if resolved:
                            imports.append(resolved)
            return imports

        # 3b. Seed from constitutionally declared workers (via IntentRepository)
        try:
            for worker_id in context.intent_repo.list_workers():
                try:
                    worker_decl = context.intent_repo.load_worker(worker_id)
                    module_path = worker_decl.get("implementation", {}).get("module")
                    if module_path:
                        resolved = resolve_import(module_path, repo_path / "src")
                        if resolved and resolved.exists():
                            seeds.add(resolved)
                            logger.debug(
                                "orphan_file_check: seeded from %s → %s",
                                worker_id,
                                resolved,
                            )
                except Exception as worker_err:
                    logger.warning(
                        "orphan_file_check: could not load worker %s: %s",
                        worker_id,
                        worker_err,
                    )
        except Exception as e:
            logger.warning("orphan_file_check: worker seeding failed: %s", e)

        # 5. BFS from seeds
        reachable: set[Path] = set()
        queue = list(seeds)
        while queue:
            current = queue.pop()
            if current in reachable:
                continue
            reachable.add(current)
            for imported in get_imports(current):
                if imported not in reachable:
                    queue.append(imported)

        # 6. Orphans = candidates not reachable
        orphans = candidate_files - reachable

        for orphan in sorted(orphans):
            rel = str(orphan.relative_to(repo_path))
            findings.append(
                AuditFinding(
                    check_id="purity.no_orphan_files",
                    severity=AuditSeverity.WARNING,
                    message=f"Orphan file: '{rel}' is not reachable from any entry point.",
                    file_path=rel,
                )
            )
            logger.debug("orphan_file_check: flagged %s", rel)

        logger.info(
            "orphan_file_check: %d/%d files reachable, %d orphans found",
            len(reachable & candidate_files),
            len(candidate_files),
            len(orphans),
        )

        return findings
