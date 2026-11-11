# src/mind/logic/engines/schema_gate.py

"""
Schema gate — JSON Schema over a record's items (ADR-173 D10).

A deterministic record engine (PROVEN): each item's chosen field is validated
against the JSON Schema given in the rule's params, with the same
``jsonschema`` library the META validator uses. It judges records only; a file
rule that names it is reported as not evaluated, never as a pass.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for

from mind.logic.record_contract import (
    RecordFinding,
    RulePart,
    engine_part,
    record_items,
)

from .base import CONTENT_NOT_EVALUATED, BaseEngine, EngineResult, EvidenceClass


# ID: d6b5fa91-f775-4231-a009-d82c658b3a2d
class SchemaGateEngine(BaseEngine):
    """Validates a field of each record item against a JSON Schema.

    Params:
        schema: dict — the JSON Schema. Required.
        field: str — the item key to validate (default ``value``).
        item_types: list[str] — only items of these types (default all).
    """

    engine_id = "schema_gate"
    evidence_class = EvidenceClass.PROVEN  # ADR-113: deterministic verdict
    supports_records: ClassVar[bool] = True

    # ID: fd151836-dbda-4227-bbc8-f4eee692e3c4
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """Files are not this engine's input: reported as not evaluated (#1050
        path), which is neither a pass nor a failure."""
        return EngineResult(
            ok=True,
            message="schema_gate judges records only; file not evaluated.",
            violations=[],
            engine_id=self.engine_id,
            extra={CONTENT_NOT_EVALUATED: "schema_gate judges records only"},
        )

    # ID: ec460c81-7d0e-4d8f-a3f6-19245faefaf5
    async def evaluate_record(
        self, record: Mapping[str, Any], rule: str, params: dict[str, Any]
    ) -> RulePart:
        """One blocking finding per schema error, naming the item and the path
        inside the field. A missing or invalid schema is a blocking finding:
        a rule that cannot check never passes."""
        schema = params.get("schema")
        field_name = params.get("field", "value")
        try:
            if not isinstance(schema, Mapping):
                raise SchemaError("the rule has no 'schema' param")
            schema = dict(schema)
            validator_cls = validator_for(schema)
            validator_cls.check_schema(schema)
        except SchemaError as exc:
            message = getattr(exc, "message", str(exc))
            return engine_part(
                self,
                rule,
                [
                    RecordFinding(
                        rule=rule,
                        message=f"schema_gate rule has no valid schema: {message}",
                        blocking=True,
                        details={"finding_type": "SCHEMA_MISCONFIGURED"},
                    )
                ],
            )
        validator = validator_cls(schema)
        findings = []
        for item_id, item in record_items(record, params.get("item_types")):
            for error in sorted(
                validator.iter_errors(item.get(field_name)),
                key=lambda e: list(map(str, e.absolute_path)),
            ):
                where = "/".join(map(str, error.absolute_path)) or "(root)"
                findings.append(
                    RecordFinding(
                        rule=rule,
                        message=f"{item_id}.{field_name} at {where}: {error.message}",
                        blocking=True,
                        item=item_id,
                    )
                )
        return engine_part(self, rule, findings)
