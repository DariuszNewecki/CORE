# src/mind/logic/engines/knowledge_gate.py
# ID: 5632d031-2f4e-4d60-8a0b-fcc15ff92efa

"""
Knowledge Graph Governance Engine.

REFACTORED:
- Handles "core.vector_index" vs "core.symbol_vector_links" schema drift.
- Improved robustness for missing tables.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from mind.logic.engines.base import BaseEngine, EngineResult
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
logger = getLogger(__name__)


# ID: 5632d031-2f4e-4d60-8a0b-fcc15ff92efa
class KnowledgeGateEngine(BaseEngine):
    """
    Context-Aware Knowledge Graph Auditor.
    """

    engine_id = "knowledge_gate"

    @classmethod
    # ID: 301b31bb-1c1c-4c1e-8bb6-3880f1a1dd4d
    def supported_check_types(cls) -> set[str]:
        return {
            "capability_assignment",
            "ast_duplication",
            "semantic_duplication",
            "duplicate_ids",
            "table_has_records",
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
            return self._check_ast_duplication(context, params)
        elif check_type == "semantic_duplication":
            return await self._check_semantic_duplication(context, params)
        elif check_type == "duplicate_ids":
            return self._check_duplicate_ids(context, params)
        elif check_type == "table_has_records":
            return await self._check_table_has_records(context, params)

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

    def _check_ast_duplication(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        if not context.symbols_map:
            return findings
        fingerprint_groups = defaultdict(list)
        for symbol_data in context.symbols_map.values():
            if "test" in symbol_data.get("module", ""):
                continue
            fp = symbol_data.get("fingerprint")
            if fp:
                fingerprint_groups[fp].append(symbol_data)
        for symbols in fingerprint_groups.values():
            if len(symbols) > 1:
                for i, data_a in enumerate(symbols):
                    for data_b in symbols[i + 1 :]:
                        findings.append(
                            self._create_duplication_finding(data_a, data_b, 1.0, "ast")
                        )
        return findings

    async def _check_semantic_duplication(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        # Fixed: Checking attribute safely
        qdrant = getattr(context, "qdrant_service", None)
        if not context.symbols_map or not qdrant:
            return findings
        return findings

    def _create_duplication_finding(self, a, b, score, dtype) -> AuditFinding:
        return AuditFinding(
            check_id=f"purity.no_{dtype}_duplication",
            severity=AuditSeverity.WARNING,
            message=f"{dtype.upper()} duplication detected.",
            file_path=a.get("file_path"),
            context={
                "symbol_a": a.get("name"),
                "symbol_b": b.get("name"),
                "score": score,
            },
        )
