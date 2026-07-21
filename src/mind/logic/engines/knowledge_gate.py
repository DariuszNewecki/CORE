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
import json
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text

from mind.logic.engines._knowledge_gate_duplication import (
    _check_ast_duplication,
    _check_semantic_duplication,
    _resolve_symbol_path,
)
from mind.logic.engines.base import BaseEngine, EngineResult, EvidenceClass
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.utils.glob_match import matches_glob


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
logger = getLogger(__name__)


# ID: 8d880004-d06c-43ba-b15e-9c934097e409
class KnowledgeGateEngine(BaseEngine):
    """
    Context-Aware Knowledge Graph Auditor.
    """

    engine_id = "knowledge_gate"
    evidence_class = EvidenceClass.PROVEN  # ADR-113: deterministic verdict
    _always_context_level: ClassVar[bool] = True  # every check_type is context-level
    requires_knowledge_graph: ClassVar[bool] = (
        True  # ADR-141 D2: must not subprocess-validate
    )

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
            "core.vector_index",  # alias — converted to symbol_vector_links below
            "core.cli_commands",
            "core.llm_resources",
            "core.cognitive_roles",
            "core.domains",
        }
    )

    # Identity column per table, for attributing a non-canonical capability
    # reference to a specific row in capability_taxonomy_whitelist findings.
    _CAPABILITY_IDENTITY_COLUMNS: ClassVar[dict[str, str]] = {
        "core.cognitive_roles": "role",
        "core.llm_resources": "name",
    }

    # Column names cannot be parameterized any more than table names can
    # (see _ALLOWED_TABLES above) — a database_sources entry is enforcement-
    # mapping YAML, the same supply-chain surface, so the column half of
    # "<schema>.<table>.<column>" is validated against this whitelist before
    # interpolation too.
    _ALLOWED_CAPABILITY_COLUMNS: ClassVar[frozenset[str]] = frozenset(
        {"required_capabilities", "provided_capabilities"}
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
            "capability_taxonomy_whitelist",
        }

    # ID: d2fa4e12-5198-462f-9615-0d286c200529
    def verify(self, file_path, params: dict[str, Any]) -> EngineResult:  # type: ignore[override]
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
        elif check_type == "capability_taxonomy_whitelist":
            return await self._check_capability_taxonomy_whitelist(context, params)

        return []

    async def _check_table_has_records(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        table_name = params.get("table")

        if not table_name:
            return []

        # SCHEMA DRIFT ALIAS:
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
                    severity=AuditSeverity.BLOCK,
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
                        severity=AuditSeverity.BLOCK,
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
                        severity=AuditSeverity.BLOCK,
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
                        severity=AuditSeverity.BLOCK,
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
        exclude_patterns = params.get("exclude_patterns", ["*tests/*", "*scripts/*"])
        for symbol_data in context.symbols_map.values():
            if not symbol_data.get("is_public") or symbol_data.get(
                "name", ""
            ).startswith("_"):
                continue
            fp = _resolve_symbol_path(symbol_data)
            if fp and any(fnmatch.fnmatch(fp, pat) for pat in exclude_patterns):
                continue
            if symbol_data.get("key") == "unassigned":
                findings.append(
                    AuditFinding(
                        check_id="linkage.capability.unassigned",
                        severity=AuditSeverity.BLOCK,
                        message=f"Public symbol '{symbol_data.get('name')}' has capability='unassigned'.",
                        file_path=symbol_data.get("file_path"),
                        line_number=symbol_data.get("line_number"),
                    )
                )
        return findings

    async def _check_capability_taxonomy_whitelist(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """Verify capability references against the canonical taxonomy.

        Two source kinds, both declared in the enforcement mapping:
        ``database_sources`` (``"<schema>.<table>.<column>"`` — a jsonb array
        column on a whitelisted table) and ``artifact_sources`` (repo-relative
        glob patterns over `.intent/` YAML/JSON). A capability value present
        in a source but absent from the taxonomy is a non-canonical-reference
        finding. A source that cannot be evaluated (taxonomy unreadable, DB
        unavailable, query failure) is an ENFORCEMENT_FAILURE finding, never a
        silent pass — per CORE-Internal-Truthfulness: absence of findings is
        evidence of compliance only when the source was actually evaluated.

        ``reject_unknown`` (present on ``no_ad_hoc_capabilities``, absent on
        ``canonical_only``) is accepted but not read: both rules currently run
        the identical canonical-membership check. That is a real, not a
        hidden, redundancy — the two rules are near-duplicates against
        today's data (see the #820 Group A disposition on retiring one of
        them) rather than the parameter implying an unimplemented distinction.
        """
        taxonomy_path = params.get("taxonomy_path")
        if not taxonomy_path:
            return [
                self._capability_taxonomy_enforcement_failure(
                    "capability_taxonomy_whitelist called without taxonomy_path "
                    "— no canonical vocabulary to check against."
                )
            ]

        resolved_taxonomy_path = self._resolve_within_repo(
            context.repo_path, taxonomy_path
        )
        if resolved_taxonomy_path is None:
            return [
                self._capability_taxonomy_enforcement_failure(
                    f"taxonomy_path '{taxonomy_path}' escapes the repository "
                    "root — refusing to load it."
                )
            ]

        try:
            taxonomy_doc = context.intent_repo.load_document(resolved_taxonomy_path)
        except Exception as exc:
            return [
                self._capability_taxonomy_enforcement_failure(
                    f"Canonical capability taxonomy at '{taxonomy_path}' could "
                    f"not be loaded: {exc}"
                )
            ]

        canonical = self._extract_canonical_capabilities(
            taxonomy_doc, params.get("taxonomy_root", "families")
        )
        if not canonical:
            return [
                self._capability_taxonomy_enforcement_failure(
                    f"Canonical capability taxonomy at '{taxonomy_path}' "
                    f"declares zero capabilities under "
                    f"'{params.get('taxonomy_root', 'families')}' — cannot "
                    "distinguish canonical from ad hoc."
                )
            ]

        findings: list[AuditFinding] = []
        for source in params.get("database_sources") or []:
            findings.extend(
                await self._check_db_capability_source(context, source, canonical)
            )
        for pattern in params.get("artifact_sources") or []:
            findings.extend(
                self._check_artifact_capability_source(context, pattern, canonical)
            )
        return findings

    @staticmethod
    def _resolve_within_repo(repo_path: Path, rel: str) -> Path | None:
        """Resolve ``rel`` under ``repo_path``, refusing any escape.

        ``repo_path / rel`` alone is not safe: pathlib's ``/`` operator
        discards the left side entirely when the right side is absolute
        (``Path("/repo") / "/etc/passwd" == Path("/etc/passwd")``), and a
        ``../``-laden relative path resolves outside the repo too. Both are
        real paths for a YAML-sourced param — the enforcement mapping is a
        governed but still supply-chain-relevant surface, the same rationale
        _ALLOWED_TABLES documents for table names.
        """
        repo_root = repo_path.resolve()
        candidate = (repo_path / rel).resolve()
        try:
            candidate.relative_to(repo_root)
        except ValueError:
            return None
        return candidate

    @staticmethod
    def _capability_taxonomy_enforcement_failure(detail: str) -> AuditFinding:
        return AuditFinding(
            check_id="capability_taxonomy_whitelist.enforcement_failure",
            severity=AuditSeverity.BLOCK,
            message=(
                f"ENFORCEMENT_FAILURE: {detail} Compliance status UNKNOWN — "
                "treat as non-compliant until fixed."
            ),
            file_path="none",
            context={"finding_type": "ENFORCEMENT_FAILURE"},
        )

    @staticmethod
    def _extract_canonical_capabilities(doc: dict[str, Any], root_key: str) -> set[str]:
        root = doc.get(root_key) if isinstance(doc, dict) else None
        if not isinstance(root, dict):
            return set()
        caps: set[str] = set()
        for family in root.values():
            if not isinstance(family, dict):
                continue
            family_caps = family.get("capabilities")
            if isinstance(family_caps, dict):
                caps.update(family_caps.keys())
        return caps

    @staticmethod
    def _coerce_capability_list(raw: Any) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(raw, list):
            return [str(v) for v in raw]
        return []

    async def _check_db_capability_source(
        self, context: AuditorContext, source: str, canonical: set[str]
    ) -> list[AuditFinding]:
        try:
            table, column = source.rsplit(".", 1)
        except ValueError:
            return [
                self._capability_taxonomy_enforcement_failure(
                    f"database_sources entry '{source}' is not a "
                    "'<schema>.<table>.<column>' reference."
                )
            ]

        if table not in self._ALLOWED_TABLES:
            return [
                AuditFinding(
                    check_id="knowledge_gate.table_not_whitelisted",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"Table '{table}' is not in the constitutional whitelist. "
                        "Add it to KnowledgeGateEngine._ALLOWED_TABLES via a "
                        "governed proposal."
                    ),
                    file_path="DB",
                )
            ]

        if column not in self._ALLOWED_CAPABILITY_COLUMNS:
            return [
                self._capability_taxonomy_enforcement_failure(
                    f"Column '{column}' on '{table}' is not a recognized "
                    "capability column "
                    f"(allowed: {sorted(self._ALLOWED_CAPABILITY_COLUMNS)})."
                )
            ]

        db_session = getattr(context, "db_session", None)
        if not db_session:
            return [
                self._capability_taxonomy_enforcement_failure(
                    f"Database source '{source}' unavailable — no db_session "
                    "in this audit context."
                )
            ]

        identity_col = self._CAPABILITY_IDENTITY_COLUMNS.get(table, "name")
        try:
            query = text(f"SELECT {identity_col}, {column} FROM {table}")
            result = await db_session.execute(query)
            rows = result.fetchall()
        except Exception as exc:
            return [
                self._capability_taxonomy_enforcement_failure(
                    f"Database source '{source}' could not be queried: {exc}"
                )
            ]

        findings: list[AuditFinding] = []
        for identity_val, raw_caps in rows:
            for cap in self._coerce_capability_list(raw_caps):
                if cap not in canonical:
                    findings.append(
                        AuditFinding(
                            check_id="capability.taxonomy.non_canonical_reference",
                            severity=AuditSeverity.BLOCK,
                            message=(
                                f"{table}.{identity_col}='{identity_val}' declares "
                                f"non-canonical capability '{cap}' in {column}."
                            ),
                            file_path="DB",
                            context={
                                "source": source,
                                "table": table,
                                "identity": str(identity_val),
                                "column": column,
                                "capability": cap,
                            },
                        )
                    )
        return findings

    def _check_artifact_capability_source(
        self, context: AuditorContext, pattern: str, canonical: set[str]
    ) -> list[AuditFinding]:
        # Routed through IntentRepository.iter_documents() rather than a raw
        # glob over `.intent/` — architecture.namespace.no_direct_protected_access.
        # matches_glob (ADR-012 sanctioned entry point) rather than fnmatch:
        # fnmatch has no real "**" semantics (requires a literal intervening
        # "/"), so a flat file directly under the pattern's directory (e.g.
        # ".intent/workers/example.yaml" against ".intent/workers/**/*")
        # would silently never match.
        findings: list[AuditFinding] = []
        capability_keys = (
            "capabilities",
            "required_capabilities",
            "provided_capabilities",
        )
        for doc_path, doc_data in context.intent_repo.iter_documents():
            try:
                rel = str(doc_path.relative_to(context.repo_path)).replace("\\", "/")
            except ValueError:
                continue
            if not matches_glob(rel, pattern):
                continue
            if not isinstance(doc_data, dict):
                continue
            for key in capability_keys:
                for cap in self._coerce_capability_list(doc_data.get(key)):
                    if cap not in canonical:
                        findings.append(
                            AuditFinding(
                                check_id="capability.taxonomy.non_canonical_reference",
                                severity=AuditSeverity.BLOCK,
                                message=(
                                    f"'{rel}' declares non-canonical capability "
                                    f"'{cap}' under '{key}'."
                                ),
                                file_path=rel,
                                context={
                                    "source": pattern,
                                    "key": key,
                                    "capability": cap,
                                },
                            )
                        )
        return findings

    # ID: fd5a8798-4e91-46e4-8a30-f9ae98479a12
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
                    level = node.level or 0
                    if level > 0:
                        # Explicit relative import (`from .x` / `from ..x`).
                        # `level` is the dot-count: the base package is `level`
                        # levels up from the importing module. Resolving from
                        # src-root or the file's own directory (the level==0
                        # paths below) cannot reach a `..`-relative target, so
                        # such files were falsely flagged orphan when reachable
                        # only via relative imports.
                        base = file_path.parent
                        for _ in range(level - 1):
                            base = base.parent
                        if node.module:
                            mod_parts = node.module.split(".")
                            for cand in (
                                base.joinpath(*mod_parts).with_suffix(".py"),
                                base.joinpath(*mod_parts, "__init__.py"),
                            ):
                                if cand.exists():
                                    imports.append(cand)
                            sub_base = base.joinpath(*mod_parts)
                        else:
                            # `from . import x` — names are submodules of base.
                            sub_base = base
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            for cand in (
                                sub_base.joinpath(alias.name).with_suffix(".py"),
                                sub_base.joinpath(alias.name, "__init__.py"),
                            ):
                                if cand.exists():
                                    imports.append(cand)
                    elif node.module:
                        resolved = resolve_import(node.module, file_path)
                        if resolved:
                            imports.append(resolved)
                        # `from X import Y` may bind submodule Y from package X;
                        # resolve each name as a potential submodule path so the
                        # BFS reaches files imported via package re-exports or
                        # FastAPI-style `from api.v1 import audit_routes` patterns.
                        # Non-submodule names (attributes, classes, functions)
                        # resolve to None and are silently ignored.
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            resolved_sub = resolve_import(
                                f"{node.module}.{alias.name}", file_path
                            )
                            if resolved_sub:
                                imports.append(resolved_sub)
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
                    # Per ADR-098 D4 / #606: parent rule purity.no_orphan_files
                    # is reporting, which rule_executor maps to INFO at dispatch.
                    check_id="purity.no_orphan_files",
                    severity=AuditSeverity.INFO,
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
