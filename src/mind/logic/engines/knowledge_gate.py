# src/mind/logic/engines/knowledge_gate.py

"""
Knowledge Graph Governance Engine.

Unlike file-scoped engines (ast_gate, glob_gate), this engine operates on the
full AuditorContext and has access to the loaded knowledge graph.

Use Cases:
- Capability assignment validation
- Cross-file dependency checks
- Domain boundary enforcement
- Knowledge graph integrity checks
- AST duplication detection (cross-file structural similarity)
- Semantic duplication detection (vector embedding similarity)
- Duplicate ID detection (cross-file UUID collisions)
- Database table validation (table existence and population)

Architecture:
- Receives AuditorContext (not individual files)
- Has access to context.symbols_map (loaded knowledge graph)
- Has access to context.qdrant_service (for semantic checks)
- Has access to context.db_session (for database checks)
- Returns findings for symbols that violate constitutional rules
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

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

    This engine enforces constitutional rules that require access to the
    full knowledge graph, not just individual files.

    Supported check_types:
    - capability_assignment: Verify symbols have capability IDs assigned
    - ast_duplication: Detect structurally identical code via AST comparison
    - semantic_duplication: Detect functionally equivalent code via vector similarity
    - duplicate_ids: Detect duplicate # ID: tags across different files
    - table_has_records: Verify database table exists and has data
    """

    engine_id = "knowledge_gate"

    @classmethod
    # ID: 59d7a38c-c5ce-489c-95be-8c64822bb1f1
    def supported_check_types(cls) -> set[str]:
        """Declare supported knowledge graph checks."""
        return {
            "capability_assignment",
            "ast_duplication",
            "semantic_duplication",
            "duplicate_ids",
            "table_has_records",
        }

    # ID: f28841c7-9602-4745-8514-b0cc01db9db0
    def verify(self, file_path, params: dict[str, Any]) -> EngineResult:
        """
        Standard BaseEngine interface (for compatibility).

        Note: This engine doesn't actually use file_path since it operates
        on the full context. Use verify_context() instead.
        """
        return EngineResult(
            ok=False,
            message="KnowledgeGateEngine requires AuditorContext. Use verify_context() instead.",
            violations=["Internal: knowledge_gate called without context"],
            engine_id=self.engine_id,
        )

    # ID: 21f029ae-a97d-4000-8372-4f813b400ea4
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Verify constitutional rules against the loaded knowledge graph.

        Args:
            context: AuditorContext with loaded symbols_map
            params: Check parameters including check_type

        Returns:
            List of AuditFindings for violations
        """
        check_type = params.get("check_type")
        if not isinstance(check_type, str) or not check_type.strip():
            return [
                AuditFinding(
                    check_id="knowledge_gate.config_error",
                    severity=AuditSeverity.ERROR,
                    message="knowledge_gate requires 'check_type' parameter",
                    file_path="N/A",
                )
            ]
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
            return self._check_table_has_records(context, params)
        else:
            return [
                AuditFinding(
                    check_id=f"knowledge_gate.{check_type}",
                    severity=AuditSeverity.ERROR,
                    message=f"Unknown knowledge_gate check_type '{check_type}'. Supported: {', '.join(self.supported_check_types())}",
                    file_path="N/A",
                )
            ]

    def _check_table_has_records(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Verify that a database table exists and has records.

        Required params:
        - table: Table name (e.g., "core.domains" or "domains")

        Optional params:
        - message: Custom error message if check fails
        """
        findings: list[AuditFinding] = []
        table_name = params.get("table")
        custom_message = params.get("message")
        if not table_name:
            return [
                AuditFinding(
                    check_id="knowledge_gate.table_has_records.config_error",
                    severity=AuditSeverity.ERROR,
                    message="table_has_records check requires 'table' parameter",
                    file_path="N/A",
                )
            ]
        db_session = getattr(context, "db_session", None)
        if not db_session:
            logger.warning(
                "No database session available in context for table_has_records check"
            )
            return findings
        try:
            query = f"SELECT EXISTS(SELECT 1 FROM {table_name} LIMIT 1)"
            result = db_session.execute(query).scalar()
            if not result:
                message = (
                    custom_message or f"Table '{table_name}' is empty or does not exist"
                )
                findings.append(
                    AuditFinding(
                        check_id="knowledge_gate.table_has_records",
                        severity=AuditSeverity.ERROR,
                        message=message,
                        file_path="N/A",
                        context={"table": table_name, "check": "table_has_records"},
                    )
                )
        except Exception as e:
            logger.error("Failed to check table '%s': %s", table_name, e)
            findings.append(
                AuditFinding(
                    check_id="knowledge_gate.table_has_records.query_failed",
                    severity=AuditSeverity.ERROR,
                    message=f"Failed to verify table '{table_name}': {e}",
                    file_path="N/A",
                    context={"table": table_name, "error": str(e)},
                )
            )
        return findings

    def _check_duplicate_ids(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Enforce linkage.duplicate_ids: Detect duplicate '# ID:' tags across the graph.
        """
        findings: list[AuditFinding] = []
        id_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for symbol_path, symbol_data in context.symbols_map.items():
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
                        message=f"Duplicate ID '{uuid_val}' found in {len(occurrences)} locations: {', '.join(locs)}",
                        file_path=occurrences[0].get("file_path"),
                        line_number=occurrences[0].get("line_number"),
                        context={"duplicates": locs, "uuid": uuid_val},
                    )
                )
        return findings

    def _check_capability_assignment(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Verify that public symbols have capability IDs assigned.
        """
        findings: list[AuditFinding] = []
        if not context.symbols_map:
            logger.warning("Knowledge graph not loaded in context.")
            return findings
        exclude_patterns = params.get("exclude_patterns", ["tests/", "scripts/"])
        unassigned_count = 0
        for symbol_path, symbol_data in context.symbols_map.items():
            if not isinstance(symbol_data, dict):
                continue
            name = symbol_data.get("name", "")
            file_path = symbol_data.get("file_path", "")
            is_public = symbol_data.get("is_public", False)
            capability = symbol_data.get("key")
            line_number = symbol_data.get("line_number")
            if (
                not is_public
                or name.startswith("_")
                or (name.startswith("__") and name.endswith("__"))
            ):
                continue
            if any(pattern in file_path for pattern in exclude_patterns):
                continue
            if capability == "unassigned":
                unassigned_count += 1
                findings.append(
                    AuditFinding(
                        check_id="linkage.capability.unassigned",
                        severity=AuditSeverity.ERROR,
                        message=f"Public symbol '{name}' has capability='unassigned'. Run 'core-admin dev sync --write'.",
                        file_path=file_path,
                        line_number=line_number,
                    )
                )
        return findings

    def _check_ast_duplication(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Detect structurally identical code via AST fingerprint comparison.
        """
        findings: list[AuditFinding] = []
        threshold = float(params.get("threshold", 0.95))
        if not context.symbols_map:
            return findings
        fingerprint_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for symbol_path, symbol_data in context.symbols_map.items():
            if not isinstance(symbol_data, dict):
                continue
            module = symbol_data.get("module", "")
            if not module or "test" in module:
                continue
            fingerprint = symbol_data.get("fingerprint")
            if not fingerprint:
                continue
            fingerprint_groups[fingerprint].append((symbol_path, symbol_data))
        for fingerprint, symbols in fingerprint_groups.items():
            if len(symbols) < 2:
                continue
            for i, (path_a, data_a) in enumerate(symbols):
                for path_b, data_b in symbols[i + 1 :]:
                    findings.append(
                        self._create_duplication_finding(data_a, data_b, 1.0, "ast")
                    )
        return findings

    async def _check_semantic_duplication(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Detect functionally equivalent code via vector similarity.
        """
        findings: list[AuditFinding] = []
        threshold = float(params.get("threshold", 0.85))
        if not context.symbols_map or not getattr(context, "qdrant_service", None):
            return findings
        qdrant_service = context.qdrant_service
        checked_pairs: set[tuple[str, str]] = set()
        relevant_symbols = {
            path: data
            for path, data in context.symbols_map.items()
            if isinstance(data, dict)
            and data.get("is_public", False)
            and ("test" not in data.get("module", ""))
        }
        vector_to_symbol = {}
        for symbol_path, symbol_data in relevant_symbols.items():
            vector_id = symbol_data.get("vector_id")
            if vector_id:
                vector_to_symbol[str(vector_id)] = (symbol_path, symbol_data)
        for symbol_path, symbol_data in relevant_symbols.items():
            vector_id = symbol_data.get("vector_id")
            if not vector_id:
                continue
            try:
                query_vector = await qdrant_service.get_vector_by_id(str(vector_id))
                results = await qdrant_service.search_similar(
                    query_vector=query_vector, limit=10
                )
                for result in results:
                    similarity = result.get("score", 0.0)
                    if similarity < threshold:
                        continue
                    payload = result.get("payload", {})
                    capability_tags = payload.get("capability_tags", [])
                    result_vector_id = capability_tags[0] if capability_tags else None
                    if not result_vector_id or str(result_vector_id) == str(vector_id):
                        continue
                    similar_match = vector_to_symbol.get(str(result_vector_id))
                    if not similar_match:
                        continue
                    similar_path, similar_data = similar_match
                    pair = tuple(sorted((symbol_path, similar_path)))
                    if pair in checked_pairs:
                        continue
                    checked_pairs.add(pair)
                    findings.append(
                        self._create_duplication_finding(
                            symbol_data, similar_data, similarity, "semantic"
                        )
                    )
            except Exception:
                continue
        return findings

    def _create_duplication_finding(
        self, symbol_a: dict, symbol_b: dict, similarity: float, duplication_type: str
    ) -> AuditFinding:
        path_a = symbol_a.get("symbol_path", "")
        name_a = path_a.split("::")[-1] if "::" in path_a else path_a
        name_b = symbol_b.get("symbol_path", "").split("::")[-1]
        return AuditFinding(
            check_id=f"purity.no_{duplication_type}_duplication",
            severity=AuditSeverity.WARNING,
            message=f"{duplication_type.upper()} duplication: '{name_a}' and '{name_b}' ({similarity:.2%})",
            file_path=symbol_a.get("module", ""),
            line_number=symbol_a.get("line_number"),
            context={
                "symbol_a": name_a,
                "symbol_b": name_b,
                "similarity": similarity,
                "type": duplication_type,
            },
        )
