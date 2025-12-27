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

Architecture:
- Receives AuditorContext (not individual files)
- Has access to context.symbols_map (loaded knowledge graph)
- Returns findings for symbols that violate constitutional rules
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mind.logic.engines.base import BaseEngine, EngineResult
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: e1f2a3b4-c5d6-7e8f-9a0b-1c2d3e4f5a6b
class KnowledgeGateEngine(BaseEngine):
    """
    Context-Aware Knowledge Graph Auditor.

    This engine enforces constitutional rules that require access to the
    full knowledge graph, not just individual files.

    Supported check_types:
    - capability_assignment: Verify symbols have capability IDs assigned
    - domain_boundary: Verify symbols respect domain boundaries
    - cross_file_dependency: Verify architectural dependencies
    """

    engine_id = "knowledge_gate"

    @classmethod
    # ID: bfb4d48b-cbae-4f3b-8c74-4ac5ef7f47f1
    def supported_check_types(cls) -> set[str]:
        """Declare supported knowledge graph checks."""
        return {
            "capability_assignment",
            # Future additions:
            # "domain_boundary",
            # "cross_file_dependency",
        }

    # ID: 36b50eae-8b86-422a-ad46-131935cd9ad1
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

    # ID: 9b07d67a-ddeb-4522-8aa5-f8381ed3daf2
    def verify_context(
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

        # Dispatch to appropriate check
        if check_type == "capability_assignment":
            return self._check_capability_assignment(context, params)
        else:
            return [
                AuditFinding(
                    check_id=f"knowledge_gate.{check_type}",
                    severity=AuditSeverity.ERROR,
                    message=f"Unknown knowledge_gate check_type '{check_type}'. "
                    f"Supported: {', '.join(self.supported_check_types())}",
                    file_path="N/A",
                )
            ]

    def _check_capability_assignment(
        self,
        context: AuditorContext,
        params: dict[str, Any],
    ) -> list[AuditFinding]:
        """
        Verify that public symbols have capability IDs assigned.

        Constitutional Rule: linkage.capability.unassigned

        Checks:
        1. Query symbols_map for all symbols
        2. Filter to public symbols (not starting with _)
        3. Exclude test files and scripts (per policy)
        4. Report symbols with capability='unassigned'

        Args:
            context: AuditorContext with loaded symbols_map
            params: Optional exclusion patterns

        Returns:
            List of AuditFindings for unassigned capabilities
        """
        findings: list[AuditFinding] = []

        if not context.symbols_map:
            logger.warning(
                "Knowledge graph not loaded in context. "
                "Run context.load_knowledge_graph() before auditing."
            )
            return findings

        logger.debug(
            "Checking capability assignments for %d symbols", len(context.symbols_map)
        )

        # Get exclusion patterns from params or use defaults
        exclude_patterns = params.get(
            "exclude_patterns",
            [
                "tests/",
                "scripts/",
            ],
        )

        unassigned_count = 0

        for symbol_path, symbol_data in context.symbols_map.items():
            # Skip if not a dict (shouldn't happen but be defensive)
            if not isinstance(symbol_data, dict):
                continue

            # Get symbol attributes
            name = symbol_data.get("name", "")
            file_path = symbol_data.get("file_path", "")
            is_public = symbol_data.get("is_public", False)
            capability = symbol_data.get("key")  # 'key' field holds capability
            line_number = symbol_data.get("line_number")

            # Exclusion: Private symbols
            if not is_public or name.startswith("_"):
                continue

            # Exclusion: Magic methods
            if name.startswith("__") and name.endswith("__"):
                continue

            # Exclusion: Files matching exclude patterns
            if any(pattern in file_path for pattern in exclude_patterns):
                continue

            # Check capability assignment
            if capability == "unassigned":
                unassigned_count += 1
                findings.append(
                    AuditFinding(
                        check_id="linkage.capability.unassigned",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Public symbol '{name}' has capability='unassigned' "
                            f"in knowledge graph. Run 'core-admin dev sync --write' "
                            f"to assign capability."
                        ),
                        file_path=file_path,
                        line_number=line_number,
                    )
                )

        logger.info(
            "Capability assignment check complete: %d unassigned symbols found",
            unassigned_count,
        )

        return findings
