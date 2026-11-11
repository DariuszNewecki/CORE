# src/mind/logic/engines/publication_gate/__init__.py

"""
Publication gate — the 10 publication rules as one record engine (ADR-173 D14).

A separate built-in module: CORE's runtime imports nothing from it by name;
the engine registry discovers it like any built-in engine, and its catalog
lives beside it (``publication_rules/``, D15). It judges records only.

The rule a requirement runs is its ``check`` param (one of ``RULES``); item
kinds, type names and relation names are params too, so the catalog, not this
code, says what an atom, model, molecule, document or catalogue is.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from mind.logic.engines.base import (
    CONTENT_NOT_EVALUATED,
    BaseEngine,
    EngineResult,
    EvidenceClass,
)
from mind.logic.record_contract import RecordFinding, RulePart, engine_part

from .rules import RULES


# ID: 8aefd017-7a16-442e-9afb-ead3795ebbe0
def catalog_path() -> Path:
    """The engine's own catalog (ADR-173 D15), beside this module."""
    return Path(__file__).resolve().parent / "publication_rules" / "catalog.yaml"


# ID: 1184e430-5f5f-475a-94c4-6bce5b245421
class PublicationGateEngine(BaseEngine):
    """Runs one of the 10 publication rules over a resolved record."""

    engine_id = "publication_gate"
    evidence_class = EvidenceClass.PROVEN  # ADR-113: deterministic structure checks
    supports_records: ClassVar[bool] = True

    # ID: 5252a5e3-456e-428a-9948-161d36d18eee
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """Files are not this engine's input: reported as not evaluated."""
        return EngineResult(
            ok=True,
            message="publication_gate judges records only; file not evaluated.",
            violations=[],
            engine_id=self.engine_id,
            extra={CONTENT_NOT_EVALUATED: "publication_gate judges records only"},
        )

    # ID: 553a558b-4caf-4d00-bb70-448ae9e572a2
    async def evaluate_record(
        self, record: Mapping[str, Any], rule: str, params: dict[str, Any]
    ) -> RulePart:
        """Run the rule named by ``params['check']``. An unknown or missing
        check is a blocking finding: a rule that cannot run never passes."""
        check = params.get("check")
        rule_fn = RULES.get(str(check))
        if rule_fn is None:
            finding = RecordFinding(
                rule=rule,
                message=f"publication_gate has no check {check!r}; known: {sorted(RULES)}",
                blocking=True,
                details={"finding_type": "CHECK_MISCONFIGURED"},
            )
            return engine_part(self, rule, [finding])
        return engine_part(self, rule, rule_fn(record, rule, params))
